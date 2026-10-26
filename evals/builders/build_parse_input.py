"""Build the parse_input datasets: messy student messages with the expected problem and steps.

Run: `uv run python -m evals.builders.build_parse_input --math-dir <dir>` where <dir> holds
train.jsonl and test.jsonl (the PRM800K `math_splits`).

The expected parse is known before the message exists. A step chain is mined from a MATH solution
(`evals.builders.mine_math`), its first line is the problem and the rest are the student's steps.
For some messages one step is made wrong on purpose (`corrupt.py`), because the parser must
transcribe a mistake, not fix it. The chain is then written as a message in a layout and a notation
(`render_message.py`). Hand-written messages (`handwritten_messages.py`) are added on top. The kind
of message is fixed by position: problem and steps, steps only (the problem is stored), the problem
only, an answer only, a question only.

    evals/datasets/dev/parse_input.jsonl
    evals/datasets/test/parse_input.jsonl
    evals/datasets/review/parse_input_build_report.json
    evals/datasets/review/parse_input_spotcheck.jsonl   (24 generated messages from dev only)

Problems go to dev or test by a hash of the MATH problem, so no problem is in both.
"""

import argparse
import hashlib
import json
import logging
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evals.builders.build_verify import load_math, write_jsonl
from evals.builders.corrupt import corrupt_pair
from evals.builders.handwritten_messages import HANDWRITTEN
from evals.builders.mine_math import (
    Chain,
    StepPair,
    _is_identity_chain,
    _variables,
    extract_chains,
    has_function_notation,
    task_type,
)
from evals.builders.render_message import LAYOUTS, NOTATIONS, notate, render_message
from evals.runner import DATASETS_DIR

logger = logging.getLogger("build_parse_input")
Record = dict[str, Any]

SUBJECTS = ("Algebra", "Prealgebra", "Intermediate Algebra")
MAX_LEVEL = 3
MAX_STEPS = 6
MAX_ITEM_LENGTH = 70
KINDS = ["full"] * 11 + ["steps_only"] * 4 + ["problem_only"] * 2 + ["answer_only"] * 2
KINDS += ["question_only"]
LAYOUT_WEIGHTS = (0.35, 0.2, 0.25, 0.2)
NOTATION_WEIGHTS = (0.4, 0.2, 0.2, 0.2)
ANSWER_FRAMES = (
    "i got {a}",
    "is the answer {a}?",
    "ans: {a}",
    "my answer is {a}",
    "so {a}, right?",
)
QUESTIONS = (
    "why do we do that first?",
    "i dont understand the first step",
    "can you give me a hint?",
    "what does it mean to isolate the variable?",
    "im stuck, where do I start?",
    "is it ok to move a term to the other side?",
    "how do I know when I am done?",
)
_SPOKEN_UNSAFE = re.compile(r"[(/^]|sqrt|abs")  # "3x squared" is ambiguous, so no powers either
_UNHANDLED = re.compile(
    r"\^(?!\(|-?(?:\d+(?:\.\d+)?|[A-Za-z]))"
)  # a power the renderers cannot read


def _tidy(text: str) -> str:
    """Drop the redundant brackets of the converter's output: `x = (19)` becomes `x = 19`."""
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s*\^\s*", "^", text)
    text = re.sub(r"\s+", " ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"(?<![\w)])\((\w+)\)", r"\1", text)
    return text


def _hash(key: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def candidate_chains(rows: list[Record], seed: int) -> list[tuple[str, str, Chain]]:
    """One usable chain per MATH problem: (hash key, unique id, tidied chain), best first."""
    found: dict[str, tuple[str, Chain]] = {}
    for row in sorted(rows, key=lambda item: _hash(item["unique_id"], seed)):
        if row["subject"] not in SUBJECTS or row["level"] > MAX_LEVEL:
            continue
        if has_function_notation(row["problem"]):
            continue
        task = task_type(row["problem"])
        usable: list[Chain] = []
        for chain in extract_chains(row["solution"]):
            items = tuple(_tidy(item) for item in chain.items)
            ok = _is_identity_chain(chain, task) and 3 <= len(items) <= MAX_STEPS + 1
            ok = ok and all(item.isascii() and len(item) <= MAX_ITEM_LENGTH for item in items)
            ok = ok and len(set(items)) == len(items)
            ok = ok and not any(_UNHANDLED.search(item) for item in items)
            ok = ok and (chain.kind != "equation" or bool(_variables(items[0])))
            if ok:
                usable.append(Chain(chain.kind, items, chain.origin))
        usable.sort(key=lambda chain: chain.kind != "equation")
        if usable:
            found[row["unique_id"]] = (row["unique_id"], usable[0])
    return [(_hash(uid, seed), uid, chain) for uid, chain in found.values()]


def _split(uid: str, seed: int) -> str:
    return "test" if int(_hash(f"split:{uid}", seed), 16) % 2 else "dev"


def _record_from_chain(uid: str, chain: Chain, kind: str, seed: int) -> Record:
    rng = random.Random(f"{seed}:{uid}")
    problem, steps = chain.items[0], list(chain.items[1:])
    layout = rng.choices(LAYOUTS, LAYOUT_WEIGHTS)[0]
    notation = rng.choices(NOTATIONS, NOTATION_WEIGHTS)[0]
    if notation == "spoken" and _SPOKEN_UNSAFE.search(" ".join(chain.items)):
        notation = "ascii"
    provenance: dict[str, Any] = {"unique_id": uid, "origin": chain.origin, "kind": chain.kind}
    features = [kind, chain.kind]
    stored: str | None = None
    expected_problem: str | None = problem
    expected_steps = steps
    if kind in ("full", "steps_only"):
        if len(steps) >= 2 and rng.random() < 0.2:
            index = rng.randrange(len(steps))
            pair = StepPair(chain.items[index], steps[index], chain.kind, chain.origin)
            wrong = corrupt_pair(pair, rng)
            if wrong is not None:
                steps[index] = wrong.text
                features.append("wrong_step")
                provenance["wrong_step"] = {"index": index, "rule": wrong.rule}
        chatty, typos = rng.random() < 0.3, rng.random() < 0.25
        features += (
            [layout, notation] + (["chatty"] if chatty else []) + (["typos"] if typos else [])
        )
        shown = problem if kind == "full" else None
        message = render_message(
            shown, steps, kind=chain.kind, layout=layout, notation=notation,
            chatty=chatty, typos=typos, rng=rng,
        )  # fmt: skip
        if kind == "steps_only":
            stored, expected_problem = problem, None
    elif kind == "problem_only":
        features.append(notation)
        message = render_message(
            problem, [], kind=chain.kind, layout="plain", notation=notation,
            chatty=False, typos=False, rng=rng,
        )  # fmt: skip
        expected_steps = []
    elif kind == "answer_only":
        stored, expected_problem, expected_steps = problem, None, []
        features.append(notation)
        message = rng.choice(ANSWER_FRAMES).format(a=notate(chain.items[-1], notation))
    else:
        stored, expected_problem, expected_steps = problem, None, []
        message = rng.choice(QUESTIONS)
    return {
        "id": f"math/{uid}",
        "message": message,
        "stored_problem": stored,
        "expected_problem": expected_problem,
        "expected_steps": expected_steps,
        "features": features,
        "source": "generated",
        "provenance": provenance,
    }


def handwritten_records() -> list[tuple[str, Record]]:
    """The hand-written messages with their split (every third one goes to test)."""
    out: list[tuple[str, Record]] = []
    for index, case in enumerate(HANDWRITTEN):
        record = {
            "id": f"hand/{index:03d}",
            "message": case["message"],
            "stored_problem": case["stored_problem"],
            "expected_problem": case["problem"],
            "expected_steps": case["steps"],
            "features": case["features"],
            "source": "handwritten",
            "provenance": {"spot_check": "pending"},
        }
        out.append(("test" if index % 3 == 2 else "dev", record))
    return out


def build(math_dir: Path, out_dir: Path, per_split: int, seed: int) -> dict[str, list[Record]]:
    candidates = candidate_chains(load_math(math_dir), seed)
    splits: dict[str, list[Record]] = {"dev": [], "test": []}
    for split in splits:
        mine = [item for item in candidates if _split(item[1], seed) == split]
        mine.sort(key=lambda item: (item[2].kind != "equation", item[0]))
        if len(mine) < per_split:
            raise ValueError(f"{split} has {len(mine)} usable chains, need {per_split}")
        chosen = sorted(mine[:per_split], key=lambda item: item[0])  # kinds in hash order
        for position, (_, uid, chain) in enumerate(chosen):
            splits[split].append(_record_from_chain(uid, chain, KINDS[position % len(KINDS)], seed))
    for split, record in handwritten_records():
        splits[split].append(record)
    for split, records in splits.items():
        write_jsonl(out_dir / split / "parse_input.jsonl", records)
    review = out_dir / "review"
    write_jsonl(review / "parse_input_spotcheck.jsonl", _spot_check(splits, seed))
    report = {
        "seed": seed,
        "per_split": per_split,
        "usable_chains": len(candidates),
        "source": "openai/prm800k math_splits (main branch), subjects " + ", ".join(SUBJECTS),
        **{split: _summary(records) for split, records in splits.items()},
    }
    (review / "parse_input_build_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return splits


def _summary(records: list[Record]) -> dict[str, Any]:
    features = Counter(f for r in records for f in r["features"])
    return {
        "n": len(records),
        "by_source": dict(Counter(r["source"] for r in records)),
        "by_feature": dict(sorted(features.items())),
        "steps_per_message": dict(
            sorted(Counter(len(r["expected_steps"]) for r in records).items())
        ),
    }


def _spot_check(splits: dict[str, list[Record]], seed: int) -> list[Record]:
    """A seeded sample of 24 generated dev messages (never test) for the developer to read."""
    generated = [r for r in splits["dev"] if r["source"] == "generated"]
    generated.sort(key=lambda record: _hash(record["id"], seed))
    return generated[:24]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DATASETS_DIR)
    parser.add_argument("--per-split", type=int, default=150)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    for split, records in build(args.math_dir, args.out_dir, args.per_split, args.seed).items():
        logger.info("%s: %d messages", split, len(records))


if __name__ == "__main__":
    main()
