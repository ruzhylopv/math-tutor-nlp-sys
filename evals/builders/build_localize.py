"""Build the localize datasets: attempts with the first error step and error type.

Run: `uv run python -m evals.builders.build_localize --math-dir <dir>` where <dir> holds
train.jsonl and test.jsonl (the PRM800K `math_splits`).

Generated cases: a step chain mined from a MATH solution (first line = problem, the rest = steps)
in which one step is made wrong by `corrupt.py`, so the first wrong step is known by construction
and the error type is `algebraic_transformation`. A chain is kept only if `verify` finds every
uncorrupted step valid and, after the corruption, the first problem it finds is a `not_valid`
verdict at exactly the corrupted step; that selection uses the code under test (see
evals/datasets/README.md). Hand-written cases (`handwritten_localize.py`) cover the other types.

    evals/datasets/dev/localize.jsonl
    evals/datasets/test/localize.jsonl
    evals/datasets/review/localize_build_report.json

Generated problems go to dev or test by a hash of the MATH `unique_id`. Hand-written cases are
grouped by problem text and each whole group goes to one split (a greedy rule that keeps both
splits covering every error type and as many kinds as possible), so no problem is in both splits.
"""

import argparse
import hashlib
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from evals.builders.build_parse_input import candidate_chains
from evals.builders.build_verify import load_math, write_jsonl
from evals.builders.corrupt import corrupt_pair
from evals.builders.handwritten_localize import HANDWRITTEN
from evals.builders.mine_math import Chain, StepPair
from evals.runner import DATASETS_DIR
from tutor.nodes.verify import verify
from tutor.state import Step, TutorState
from tutor.tools.diagnosis import VALID_RELATIONS

logger = logging.getLogger("build_localize")
Record = dict[str, Any]


def _split(uid: str, seed: int) -> str:
    """The same MATH problem always lands in the same split for a given seed."""
    digest = hashlib.sha256(f"{seed}:localize-split:{uid}".encode()).hexdigest()
    return "test" if int(digest, 16) % 2 else "dev"


def _first_problem(problem: str, claims: list[str]) -> tuple[int, str] | None:
    """The first step `verify` does not accept as valid: (1-based index, relation), or None."""
    state: TutorState = {"problem": problem, "student_steps": [Step(claim=c) for c in claims]}
    for verdict in verify(state)["step_verdicts"]:
        if verdict.relation not in VALID_RELATIONS:
            return verdict.step_index, str(verdict.relation)
    return None


def generated_record(uid: str, chain: Chain, seed: int) -> Record | None:
    """One attempt with a corrupted step, or None if the chain or corruption does not qualify."""
    problem, steps = chain.items[0], list(chain.items[1:])
    if _first_problem(problem, steps) is not None:
        return None  # the checker does not accept the uncorrupted chain
    rng = random.Random(f"{seed}:localize:{uid}")
    index = rng.randrange(len(steps))
    pair = StepPair(chain.items[index], steps[index], chain.kind, chain.origin)
    wrong = corrupt_pair(pair, rng)
    if wrong is None:
        return None
    steps[index] = wrong.text
    if _first_problem(problem, steps) != (index + 1, "not_valid"):
        return None
    return {
        "id": f"math/{uid}#{index + 1}",
        "problem": problem,
        "steps": [{"claim": c, "justification": "", "justification_claim": None} for c in steps],
        "expected": {
            "first_error_step": index + 1,
            "focus_step": index + 1,
            "error_type": "algebraic_transformation",
        },
        "kind": "generated_not_valid",
        "source": "generated",
        "provenance": {"unique_id": uid, "origin": chain.origin, "rule": wrong.rule, "seed": seed},
    }


def _assign_groups(groups: dict[str, list[Record]]) -> dict[str, str]:
    """Problem text -> split, deterministic and greedy.

    Biggest groups first (ties by text). A group goes to the split where it adds the most error
    types not yet covered, then the most kinds not yet covered, then to the smaller split, then dev.
    """
    seen: dict[str, dict[str, set[str]]] = {
        split: {"types": set(), "kinds": set()} for split in ("dev", "test")
    }
    size = {"dev": 0, "test": 0}
    assignment: dict[str, str] = {}
    for problem in sorted(groups, key=lambda text: (-len(groups[text]), text)):
        types = {str(r["expected"]["error_type"]) for r in groups[problem]}
        kinds = {str(r["kind"]) for r in groups[problem]}

        def score(split: str, types: set[str] = types, kinds: set[str] = kinds) -> tuple[int, ...]:
            return (
                len(types - seen[split]["types"]),
                len(kinds - seen[split]["kinds"]),
                -size[split],
            )

        split = "test" if score("test") > score("dev") else "dev"
        assignment[problem] = split
        seen[split]["types"] |= types
        seen[split]["kinds"] |= kinds
        size[split] += len(groups[problem])
    return assignment


def handwritten_records() -> list[tuple[str, Record]]:
    """The hand-written cases with their split. All cases on one problem go to the same split."""
    records: list[Record] = [
        {
            "id": f"hand/{index:03d}",
            "problem": case["problem"],
            "steps": case["steps"],
            "expected": case["expected"],
            "kind": case["kind"],
            "source": "handwritten",
            "provenance": {"spot_check": "pending"},
        }
        for index, case in enumerate(HANDWRITTEN)
    ]
    groups: dict[str, list[Record]] = {}
    for record in records:
        groups.setdefault(record["problem"], []).append(record)
    assignment = _assign_groups(groups)
    return [(assignment[record["problem"]], record) for record in records]


def build(math_dir: Path, out_dir: Path, per_split: int, seed: int) -> dict[str, list[Record]]:
    candidates = candidate_chains(load_math(math_dir), seed)
    splits: dict[str, list[Record]] = {"dev": [], "test": []}
    tried: Counter[str] = Counter()
    for _, uid, chain in sorted(candidates, key=lambda item: item[0]):
        split = _split(uid, seed)
        if len(splits[split]) >= per_split:
            continue
        tried[split] += 1
        record = generated_record(uid, chain, seed)
        if record is not None:
            splits[split].append(record)
    for split, records in splits.items():
        if len(records) < per_split:
            raise ValueError(f"{split} has {len(records)} usable attempts, need {per_split}")
    for split, record in handwritten_records():
        splits[split].append(record)
    for split, records in splits.items():
        write_jsonl(out_dir / split / "localize.jsonl", records)
    report = {
        "seed": seed,
        "per_split": per_split,
        "chains_tried": dict(tried),
        **{split: _summary(records) for split, records in splits.items()},
    }
    review = out_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    (review / "localize_build_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return splits


def _summary(records: list[Record]) -> dict[str, Any]:
    types = Counter(str(r["expected"]["error_type"] or "none") for r in records)
    return {
        "n": len(records),
        "by_source": dict(Counter(r["source"] for r in records)),
        "by_kind": dict(sorted(Counter(r["kind"] for r in records).items())),
        "by_error_type": dict(sorted(types.items())),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DATASETS_DIR)
    parser.add_argument("--per-split", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    for split, records in build(args.math_dir, args.out_dir, args.per_split, args.seed).items():
        logger.info("%s: %d attempts", split, len(records))


if __name__ == "__main__":
    main()
