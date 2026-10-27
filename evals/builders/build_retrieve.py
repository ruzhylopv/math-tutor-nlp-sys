"""Build the retrieve datasets: the student's wrong step and the catalogue entry it shows.

Run: `uv run python -m evals.builders.build_retrieve` (no outside data is needed).

Generated queries: for every catalogue entry with a mechanical wrong rule
(`misconception_rules.py`), a few draws of (correct line, wrong line); SymPy confirmed each
wrong line is really wrong, so the true misconception is known by construction. A second set
wraps both lines in the same larger expression (`generated_wrapped`), so their shape is no
longer the catalogue example's. Hand-written
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
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evals.builders.build_verify import write_jsonl
from evals.builders.handwritten_queries import HANDWRITTEN, UNREACHABLE
from evals.builders.misconception_rules import RULES, draw, draw_wrapped
from evals.runner import DATASETS_DIR
from tutor.state import CatalogueEntry
from tutor.tools.catalogue import load_catalogue

logger = logging.getLogger("build_retrieve")
Record = dict[str, Any]


def _split(entry_id: str) -> str:
    """Entries alternate between dev and test (M001 dev, M002 test, ...), so both splits cover
    every category and no entry is in both."""
    return "dev" if int(entry_id[1:]) % 2 else "test"


def _generated(
    entry: CatalogueEntry,
    draw_fn: Callable[[str, random.Random], tuple[str, str] | None],
    source: str,
    seed_tag: str,
    count: int,
    seed: int,
) -> list[Record]:
    """Up to `count` distinct (correct line, wrong line) queries for a rule."""
    records: list[Record] = []
    seen: set[tuple[str, str]] = set()
    for index in range(count * 3):
        if len(records) >= count:
            break
        pair = draw_fn(entry.id, random.Random(f"{seed}:{seed_tag}{entry.id}:{index}"))
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        records.append(
            {
                "id": f"{'gen' if source == 'generated' else 'wrap'}/{entry.id}#{index}",
                "problem": pair[0],
                "steps": [{"claim": pair[1], "justification": ""}],
                "focus_step": 1,
                "error_type": "algebraic_transformation",
                "topic": entry.topic,
                "expected": entry.id,
                "category": entry.category,
                "source": source,
                "provenance": {"rule": entry.id, "seed": seed},
            }
        )
    return records


def build(
    out_dir: Path, per_rule: int, wrapped_per_rule: int, seed: int
) -> dict[str, list[Record]]:
    catalogue = {entry.id: entry for entry in load_catalogue()}
    splits: dict[str, list[Record]] = {"dev": [], "test": []}
    for entry_id, entry in catalogue.items():
        if entry_id not in RULES:
            continue
        records = _generated(entry, draw, "generated", "", per_rule, seed)
        records += _generated(
            entry, draw_wrapped, "generated_wrapped", "wrap:", wrapped_per_rule, seed
        )
        splits[_split(entry_id)] += records
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
    for split, records in splits.items():
        write_jsonl(out_dir / split / "retrieve.jsonl", records)
    review = out_dir / "review"
    review.mkdir(parents=True, exist_ok=True)
    report = {
        "seed": seed,
        "per_rule": per_rule,
        "wrapped_per_rule": wrapped_per_rule,
        "catalogue_entries": len(catalogue),
        "entries_with_a_rule": len(RULES),
        "entries_without_any_query": sorted(set(catalogue) - covered - UNREACHABLE),
        "unreachable_entries": sorted(UNREACHABLE),
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
    parser.add_argument("--wrapped-per-rule", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    for split, records in build(
        args.out_dir, args.per_rule, args.wrapped_per_rule, args.seed
    ).items():
        logger.info("%s: %d queries", split, len(records))


if __name__ == "__main__":
    main()
