"""Build the verify step datasets from MATH, rule-based corruptions and hand-written cases.

Run: `uv run python -m evals.builders.build_verify --math-dir <dir>` where <dir> holds train.jsonl
and test.jsonl.
The MATH files are the PRM800K `math_splits` (JSONL with problem, solution, subject, level,
unique_id). Raw downloads stay outside the repo; only the small derived files are written:

    evals/datasets/dev/verify_steps.jsonl
    evals/datasets/test/verify_steps.jsonl
    evals/datasets/review/verify_steps_disagreements.jsonl

Split: mined and generated cases by source problem, with a fixed seed, so no problem is in both
dev and test; hand-written cases stratified by relation. A mined pair
is kept as `equivalent` only if SymPy agrees; pairs SymPy calls anything else go to the review file
(author typo, condition-dependent line, or checker bug) instead of being dropped silently.
"""

import argparse
import hashlib
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from evals.builders.corrupt import corrupt_pair
from evals.builders.handwritten import HANDWRITTEN
from evals.builders.mine_math import (
    extract_chains,
    has_function_notation,
    pairs_from_chains,
    task_type,
)
from evals.runner import DATASETS_DIR
from tutor.tools.algebra import step_relation

logger = logging.getLogger("build_verify")
TEST_PERCENT = 30
Record = dict[str, Any]


def load_math(math_dir: Path) -> list[Record]:
    rows: list[Record] = []
    for name in ("train.jsonl", "test.jsonl"):
        with (math_dir / name).open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def split_of(key: str, seed: int) -> str:
    """The same key always lands in the same split for a given seed."""
    digest = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return "test" if int(digest, 16) % 100 < TEST_PERCENT else "dev"


def _record(
    record_id: str, task: str, problem: str, prev: str, curr: str, relation: str, **extra: Any
) -> Record:
    return {
        "id": record_id,
        "task_type": task,
        "problem": problem,
        "prev": prev,
        "curr": curr,
        "relation": relation,
        "original": extra.pop("original", None),
        **extra,
    }


Mined = tuple[list[tuple[str, Record]], list[Record], Counter[str]]


def mine_records(rows: list[Record], seed: int) -> Mined:
    """Positives and generated negatives (with their split key), review cases, and counts."""
    kept: list[tuple[str, Record]] = []
    review: list[Record] = []
    counts: Counter[str] = Counter()
    for row in rows:
        if row["subject"] != "Algebra" or row["level"] not in (1, 2, 3):
            continue
        if has_function_notation(row["problem"]):
            counts["problems skipped (function notation or custom operation)"] += 1
            continue
        task = task_type(row["problem"])
        problem, key = row["problem"], row["unique_id"]
        for index, pair in enumerate(pairs_from_chains(extract_chains(row["solution"]), task)):
            base = f"math/{key}#{index}"
            provenance = {"unique_id": key, "origin": pair.origin, "kind": pair.kind}
            relation = step_relation(pair.prev, pair.curr)
            if relation == "unparsable":
                counts["mined pairs dropped (unparsable)"] += 1
                continue
            positive = _record(
                base, task, problem, pair.prev, pair.curr, "equivalent",
                source="math", provenance=provenance,
            )  # fmt: skip
            if relation != "equivalent":
                counts["mined pairs sent to review"] += 1
                review.append({**positive, "checker_says": relation})
                continue
            counts["mined positives"] += 1
            kept.append((key, positive))
            corruption = corrupt_pair(pair, random.Random(f"{seed}:{base}"))
            if corruption is None:
                counts["positives without a witnessed corruption"] += 1
                continue
            counts["generated negatives"] += 1
            negative = _record(
                f"gen/{base}", task, problem, pair.prev, corruption.text, "not_valid",
                source="generated",
                provenance={**provenance, "rule": corruption.rule, "seed": seed},
            )  # fmt: skip
            kept.append((key, negative))
    return kept, review, counts


def handwritten_records() -> list[tuple[str, Record]]:
    """Hand-written cases with their split.

    They share problem texts across relations, so they are split stratified by relation (every
    third case of each relation goes to test), not by problem; otherwise the rare relations would
    be nearly absent from one split.
    """
    seen: Counter[str] = Counter()
    records: list[tuple[str, Record]] = []
    for index, case in enumerate(HANDWRITTEN):
        rank = seen[case["relation"]]
        seen[case["relation"]] += 1
        record = _record(
            f"hand/{index:03d}", case["task_type"], case["problem"], case["prev"], case["curr"],
            case["relation"], original=case["original"], source="handwritten",
            provenance={"author": "agent", "spot_check": "pending"},
        )  # fmt: skip
        records.append(("test" if rank % 3 == 2 else "dev", record))
    return records


def write_jsonl(path: Path, records: list[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda record: record["id"])
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in ordered),
        encoding="utf-8",
    )


def build(math_dir: Path, out_dir: Path, seed: int) -> Counter[str]:
    kept, review, counts = mine_records(load_math(math_dir), seed)
    by_split: dict[str, list[Record]] = {"dev": [], "test": []}
    for key, record in kept:
        by_split[split_of(key, seed)].append(record)
    for split, record in handwritten_records():
        by_split[split].append(record)
    for split, records in by_split.items():
        write_jsonl(out_dir / split / "verify_steps.jsonl", records)
        counts.update(f"{split}: {r['source']}/{r['relation']}" for r in records)
    write_jsonl(out_dir / "review" / "verify_steps_disagreements.jsonl", review)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DATASETS_DIR)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    for name, count in sorted(build(args.math_dir, args.out_dir, args.seed).items()):
        logger.info("%-60s %d", name, count)


if __name__ == "__main__":
    main()
