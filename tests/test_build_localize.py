import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from evals.builders import build_localize
from evals.builders.build_localize import build, generated_record, handwritten_records
from evals.builders.corrupt import Corruption
from evals.builders.handwritten_localize import HANDWRITTEN
from evals.builders.mine_math import Chain
from tutor.nodes.verify import verify
from tutor.state import Step, TutorState
from tutor.tools.diagnosis import VALID_RELATIONS


def _math_dir(tmp_path: Path, problems: int = 80) -> Path:
    rows = []
    for i in range(problems):
        a, b = 2 + i % 7, 3 + i
        solution = (
            "\\begin{align*}\n"
            f"{a}x+{b}&={a * 5 + b}\\\\\n{a}x&={a * 5}\\\\\nx&=5\n\\end{{align*}}"
        )
        rows.append(
            {
                "unique_id": f"train/algebra/{i}.json",
                "subject": "Algebra",
                "level": 1 + i % 3,
                "problem": f"Solve for x in the equation {a}x+{b}={a * 5 + b}.",
                "solution": solution,
            }
        )
    folder = tmp_path / "math"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "train.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    (folder / "test.jsonl").write_text("", encoding="utf-8")
    return folder


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _build(tmp_path: Path, per_split: int = 5) -> tuple[Path, dict[str, list[dict[str, Any]]]]:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, per_split=per_split, seed=0)
    return out, {s: _read(out / s / "localize.jsonl") for s in ("dev", "test")}


def test_each_split_has_the_requested_generated_attempts_plus_hand_written_ones(
    tmp_path: Path,
) -> None:
    _, splits = _build(tmp_path)
    handwritten = Counter(split for split, _ in handwritten_records())
    for split, records in splits.items():
        assert sum(r["source"] == "generated" for r in records) == 5
        assert sum(r["source"] == "handwritten" for r in records) == handwritten[split]


def test_a_problem_is_in_one_split_only(tmp_path: Path) -> None:
    """Compared by problem text, generated and hand-written cases together."""
    _, splits = _build(tmp_path)
    problems = {s: {r["problem"] for r in rs} for s, rs in splits.items()}
    assert problems["dev"] and problems["test"]
    assert problems["dev"].isdisjoint(problems["test"])


def test_the_hand_written_problems_are_in_one_split_only() -> None:
    splits: dict[str, set[str]] = {"dev": set(), "test": set()}
    for split, record in handwritten_records():
        splits[split].add(record["problem"])
    assert splits["dev"].isdisjoint(splits["test"])


def test_a_generated_label_is_the_corrupted_step_and_the_pipeline_agrees(tmp_path: Path) -> None:
    _, splits = _build(tmp_path, per_split=10)
    for records in splits.values():
        for record in (r for r in records if r["source"] == "generated"):
            index = record["expected"]["first_error_step"]
            assert record["id"].endswith(f"#{index}")
            assert record["expected"] == {
                "first_error_step": index,
                "focus_step": index,
                "error_type": "algebraic_transformation",
            }
            state: TutorState = {
                "problem": record["problem"],
                "student_steps": [Step(claim=s["claim"]) for s in record["steps"]],
            }
            verdicts = verify(state)["step_verdicts"]
            assert verdicts[index - 1].relation == "not_valid"
            assert all(v.relation in VALID_RELATIONS for v in verdicts[: index - 1])
            assert record["provenance"]["rule"]


def test_a_chain_the_checker_does_not_accept_is_skipped() -> None:
    bad = Chain("equation", ("2x + 3 = 11", "2x = 100", "x = 4"), "align")  # already invalid
    assert generated_record("u", bad, seed=0) is None


def test_the_build_is_reproducible(tmp_path: Path) -> None:
    first, _ = _build(tmp_path / "a")
    second, _ = _build(tmp_path / "b")
    for split in ("dev", "test"):
        name = f"{split}/localize.jsonl"
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_the_report_is_written(tmp_path: Path) -> None:
    out, _ = _build(tmp_path)
    report = json.loads((out / "review" / "localize_build_report.json").read_text("utf-8"))
    assert report["per_split"] == 5 and report["dev"]["n"] >= 5


def test_too_few_usable_attempts_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="usable attempts"):
        build(_math_dir(tmp_path, problems=4), tmp_path / "out", per_split=50, seed=0)


def test_the_hand_written_cases_are_well_formed_and_cover_every_type() -> None:
    assert len(HANDWRITTEN) >= 25
    problems_steps = [(c["problem"], tuple(s["claim"] for s in c["steps"])) for c in HANDWRITTEN]
    assert len(set(problems_steps)) == len(problems_steps)
    types = {c["expected"]["error_type"] for c in HANDWRITTEN}
    assert types == {
        "algebraic_transformation",
        "omission_extraneous_root",
        "reasoning_result_mismatch",
        "other",
        None,
    }
    for case in HANDWRITTEN:
        first, focus = case["expected"]["first_error_step"], case["expected"]["focus_step"]
        for number in (first, focus):
            assert number is None or 1 <= number <= len(case["steps"])
        if first is not None:
            assert first == focus  # a first error step is also the step to talk about


def test_both_splits_see_every_error_type_and_every_kind_the_grouping_allows() -> None:
    types: dict[str, set[Any]] = {"dev": set(), "test": set()}
    kinds: dict[str, set[str]] = {"dev": set(), "test": set()}
    problems_per_kind: dict[str, set[str]] = {}
    for split, record in handwritten_records():
        types[split].add(record["expected"]["error_type"])
        kinds[split].add(record["kind"])
        problems_per_kind.setdefault(record["kind"], set()).add(record["problem"])
    assert types["dev"] == types["test"]
    # a kind that occurs on 2+ problems can be in both splits; one problem stays in one split
    splittable = {kind for kind, problems in problems_per_kind.items() if len(problems) >= 2}
    assert splittable
    assert splittable <= kinds["dev"] and splittable <= kinds["test"]


def _patched_corruption(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(build_localize, "corrupt_pair", lambda pair, rng: Corruption(text, "x"))


def _uid_with_first_step_chosen(seed: int) -> str:
    for number in range(1000):
        uid = f"u{number}"
        if random.Random(f"{seed}:localize:{uid}").randrange(2) == 0:
            return uid
    raise AssertionError("no uid found")


@pytest.mark.parametrize(
    ("replacement", "why"),
    [
        ("x equals three", "the corrupted step is unparsable, not not_valid"),
        ("x = 2", "the corruption is still a valid step"),
        ("x^2 = 4", "the corrupted step is valid but the next, original step is not_valid"),
    ],
)
def test_a_corruption_the_checker_does_not_flag_as_not_valid_at_that_step_is_skipped(
    monkeypatch: pytest.MonkeyPatch, replacement: str, why: str
) -> None:
    # the clean chain is accepted: x = 2 is equivalent to the problem, (x - 2)(x - 3) = 0 follows
    chain = Chain("equation", ("x - 1 = 1", "x = 2", "(x - 2)(x - 3) = 0"), "align")
    assert build_localize._first_problem(chain.items[0], list(chain.items[1:])) is None
    _patched_corruption(monkeypatch, replacement)
    assert generated_record(_uid_with_first_step_chosen(0), chain, seed=0) is None, why
