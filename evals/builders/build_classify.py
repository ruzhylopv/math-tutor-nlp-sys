"""Build the classify datasets: MATH problems with their own subject and level labels.

Run: `uv run python -m evals.builders.build_classify --math-dir <dir>` where <dir> holds train.jsonl
and test.jsonl (the PRM800K `math_splits`). The labels are the human-assigned `subject` and
`level` of MATH, so they do not depend on our code. Per subject, problems are ordered by a seeded
hash, the first N go to dev and the next N to test, so the splits are disjoint and stratified by
subject. Identical problem texts are kept once.

    evals/datasets/dev/classify.jsonl
    evals/datasets/test/classify.jsonl
    evals/datasets/review/classify_build_report.json
"""

import argparse
import hashlib
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from evals.runner import DATASETS_DIR

logger = logging.getLogger("build_classify")
Record = dict[str, Any]


def load_math(math_dir: Path) -> list[Record]:
    rows: list[Record] = []
    for name in ("train.jsonl", "test.jsonl"):
        with (math_dir / name).open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def _order(row: Record, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{row['unique_id']}".encode()).hexdigest()


def build(math_dir: Path, out_dir: Path, per_subject: int, seed: int) -> dict[str, list[Record]]:
    seen: set[str] = set()
    by_subject: dict[str, list[Record]] = {}
    for row in sorted(load_math(math_dir), key=lambda item: _order(item, seed)):
        if row["problem"] in seen:
            continue
        seen.add(row["problem"])
        by_subject.setdefault(row["subject"], []).append(row)
    splits: dict[str, list[Record]] = {"dev": [], "test": []}
    for subject, rows in sorted(by_subject.items()):
        if len(rows) < 2 * per_subject:
            raise ValueError(f"{subject} has {len(rows)} problems, need {2 * per_subject}")
        for split, chunk in (
            ("dev", rows[:per_subject]),
            ("test", rows[per_subject : 2 * per_subject]),
        ):
            splits[split] += [
                {
                    "id": r["unique_id"],
                    "problem": r["problem"],
                    "subject": r["subject"],
                    "level": r["level"],
                }
                for r in chunk
            ]
    for split, records in splits.items():
        path = out_dir / split / "classify.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(records, key=lambda record: record["id"])
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ordered), encoding="utf-8"
        )
    report = {
        "seed": seed,
        "per_subject": per_subject,
        "source": "openai/prm800k math_splits (main branch)",
        **{
            split: {
                "n": len(records),
                "by_subject": dict(Counter(r["subject"] for r in records)),
                "by_level": dict(sorted(Counter(r["level"] for r in records).items())),
            }
            for split, records in splits.items()
        },
    }
    report_path = out_dir / "review" / "classify_build_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return splits


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DATASETS_DIR)
    parser.add_argument("--per-subject", type=int, default=60)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    for split, records in build(args.math_dir, args.out_dir, args.per_subject, args.seed).items():
        logger.info("%s: %d problems", split, len(records))


if __name__ == "__main__":
    main()
