"""Build the hint datasets from the retrieve datasets: wrong steps with a known misconception.

Run: `uv run python -m evals.builders.build_hint [--splits dev test]` after the retrieve datasets
exist. It reads `evals/datasets/<split>/retrieve.jsonl` and does not change it.

Each case is a retrieve query (the problem, the student's steps, the focus step, the entry the
step shows) plus a hint `level` from 1 to 4. All hand-written queries are kept; then up to `--size`
cases in all are filled from the generated ones, one category at a time in turn, alternating
`generated_wrapped` and `generated` (the wrapped ones are the more realistic). The order inside a
group is a hash of the id, so the choice is deterministic. Levels are dealt in turn over the cases
by id, so each level has about a quarter of them.

    evals/datasets/dev/hint.jsonl
    evals/datasets/test/hint.jsonl   (protected: the developer runs the builder for this one)
"""

import argparse
import hashlib
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from evals.builders.build_verify import write_jsonl
from evals.runner import DATASETS_DIR, load_jsonl

logger = logging.getLogger("build_hint")
Record = dict[str, Any]
LEVELS = 4
GENERATED_SOURCES = ("generated_wrapped", "generated")


def _key(record: Record) -> str:
    return hashlib.sha256(str(record["id"]).encode()).hexdigest()


def select(queries: list[Record], size: int) -> list[Record]:
    """All hand-written queries, then generated ones in turn over categories and sources."""
    chosen = [q for q in queries if q["source"] == "handwritten"]
    groups: dict[tuple[str, str], list[Record]] = {}
    for query in sorted(queries, key=_key):
        if query["source"] in GENERATED_SOURCES:
            groups.setdefault((query["source"], query["category"]), []).append(query)
    order = [
        groups[(source, category)]
        for category in sorted({c for _, c in groups})
        for source in GENERATED_SOURCES
        if (source, category) in groups
    ]
    while len(chosen) < size and any(order):
        for queue in order:
            if queue and len(chosen) < size:
                chosen.append(queue.pop(0))
    return sorted(chosen, key=lambda record: str(record["id"]))


def build_split(queries: list[Record], size: int) -> list[Record]:
    cases = select(queries, size)
    return [{**case, "level": 1 + number % LEVELS} for number, case in enumerate(cases)]


def build(out_dir: Path, splits: list[str], size: int) -> dict[str, list[Record]]:
    built: dict[str, list[Record]] = {}
    for split in splits:
        queries = load_jsonl(out_dir / split / "retrieve.jsonl")
        built[split] = build_split(queries, size)
        write_jsonl(out_dir / split / "hint.jsonl", built[split])
        logger.info(
            "%s: %d cases, by source %s, by level %s",
            split,
            len(built[split]),
            dict(Counter(r["source"] for r in built[split])),
            dict(sorted(Counter(r["level"] for r in built[split]).items())),
        )
    return built


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DATASETS_DIR)
    parser.add_argument("--splits", nargs="+", choices=("dev", "test"), default=["dev", "test"])
    parser.add_argument("--size", type=int, default=60)
    args = parser.parse_args()
    build(args.out_dir, args.splits, args.size)


if __name__ == "__main__":
    main()
