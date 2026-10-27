"""Build the retrieve datasets: the student's wrong step and the catalogue entry it shows.

Run: `uv run python -m evals.builders.build_retrieve` (no outside data is needed).

Generated queries: for every catalogue entry with a mechanical wrong rule
(`misconception_rules.py`), a few draws of (correct line, wrong line); SymPy confirmed each
wrong line is really wrong, so the true misconception is known by construction. Hand-written
queries (`handwritten_queries.py`) cover the other entries. Every query is the state
`retrieve` reads: the correct line as `problem`, the wrong line as step 1 (or the hand-written
steps), `focus_step`, `error_type` and the entry's `topic`. Entries go to dev or test by a
hash of their id, with their queries, so no entry is in both splits.

    evals/datasets/dev/retrieve.jsonl
    evals/datasets/test/retrieve.jsonl
    evals/datasets/review/retrieve_build_report.json
"""

import argparse
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from evals.builders.build_verify import write_jsonl
from evals.builders.handwritten_queries import HANDWRITTEN
from evals.builders.misconception_rules import RULES, draw
from evals.runner import DATASETS_DIR
from tutor.tools.catalogue import load_catalogue

logger = logging.getLogger("build_retrieve")
Record = dict[str, Any]


def _split(entry_id: str) -> str:
    """Entries alternate between dev and test (M001 dev, M002 test, ...), so both splits cover
    every category and no entry is in both."""
    return "dev" if int(entry_id[1:]) % 2 else "test"


def build(out_dir: Path, per_rule: int, seed: int) -> dict[str, list[Record]]:
    catalogue = {entry.id: entry for entry in load_catalogue()}
    splits: dict[str, list[Record]] = {"dev": [], "test": []}
    for entry_id, entry in catalogue.items():
        if entry_id not in RULES:
            continue
        seen: set[tuple[str, str]] = set()
        for index in range(per_rule * 3):
            if len([r for r in splits[_split(entry_id)] if r["expected"] == entry_id]) >= per_rule:
                break
            pair = draw(entry_id, random.Random(f"{seed}:{entry_id}:{index}"))
            if pair is None or pair in seen:
                continue
            seen.add(pair)
            previous, wrong = pair
            splits[_split(entry_id)].append(
                {
                    "id": f"gen/{entry_id}#{index}",
                    "problem": previous,
                    "steps": [{"claim": wrong, "justification": ""}],
                    "focus_step": 1,
                    "error_type": "algebraic_transformation",
                    "topic": entry.topic,
                    "expected": entry_id,
                    "category": entry.category,
                    "source": "generated",
                    "provenance": {"rule": entry_id, "seed": seed},
                }
            )
    for number, query in enumerate(HANDWRITTEN):
        entry = catalogue[query["expected"]]
        splits[_split(entry.id)].append(
            {
                "id": f"hand/{number:03d}",
                "problem": query["problem"],
                "steps": query["steps"],
                "focus_step": query["focus_step"],
                "error_type": query["error_type"],
                "topic": entry.topic,
                "expected": entry.id,
                "category": entry.category,
                "source": "handwritten",
                "provenance": {"spot_check": "pending"},
            }
        )
    covered = {r["expected"] for records in splits.values() for r in records}
    dropped = sorted(set(catalogue) - covered)
    for split, records in splits.items():
        write_jsonl(out_dir / split / "retrieve.jsonl", records)
    review = out_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    report = {
        "seed": seed,
        "per_rule": per_rule,
        "catalogue_entries": len(catalogue),
        "entries_with_a_rule": len(RULES),
        "entries_without_any_query": dropped,
        **{split: _summary(records) for split, records in splits.items()},
    }
    (review / "retrieve_build_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return splits


def _summary(records: list[Record]) -> dict[str, Any]:
    return {
        "n": len(records),
        "entries": len({r["expected"] for r in records}),
        "by_source": dict(Counter(r["source"] for r in records)),
        "by_category": dict(sorted(Counter(r["category"] for r in records).items())),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DATASETS_DIR)
    parser.add_argument("--per-rule", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    for split, records in build(args.out_dir, args.per_rule, args.seed).items():
        logger.info("%s: %d queries", split, len(records))


if __name__ == "__main__":
    main()
