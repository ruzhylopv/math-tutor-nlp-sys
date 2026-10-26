import json
from pathlib import Path
from typing import Any

import pytest

from evals.builders.build_parse_input import KINDS, _tidy, build
from evals.builders.handwritten_messages import HANDWRITTEN


def _math_dir(tmp_path: Path, problems: int = 60) -> Path:
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


def _build(
    tmp_path: Path, per_split: int = 20, problems: int = 60
) -> tuple[Path, dict[str, list[dict[str, Any]]]]:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path, problems), out, per_split=per_split, seed=0)
    return out, {s: _read(out / s / "parse_input.jsonl") for s in ("dev", "test")}


def test_each_split_has_the_requested_generated_messages_and_the_hand_written_ones(
    tmp_path: Path,
) -> None:
    _, splits = _build(tmp_path)
    for split, records in splits.items():
        generated = [r for r in records if r["source"] == "generated"]
        hand = [r for r in records if r["source"] == "handwritten"]
        assert len(generated) == 20
        expected_hand = sum(1 for i in range(len(HANDWRITTEN)) if (i % 3 == 2) == (split == "test"))
        assert len(hand) == expected_hand


def test_a_problem_is_in_one_split_only(tmp_path: Path) -> None:
    _, splits = _build(tmp_path)
    ids = {
        s: {r["id"] for r in records if r["source"] == "generated"} for s, records in splits.items()
    }
    assert ids["dev"].isdisjoint(ids["test"])


def test_every_kind_of_message_appears_and_matches_its_expected_parse(tmp_path: Path) -> None:
    _, splits = _build(tmp_path, per_split=len(KINDS))
    for records in splits.values():
        generated = [r for r in records if r["source"] == "generated"]
        kinds = {r["features"][0] for r in generated}
        assert kinds == set(KINDS)
        for r in generated:
            kind = r["features"][0]
            if kind == "full":
                assert r["stored_problem"] is None and r["expected_problem"]
                assert r["expected_steps"]
            elif kind == "steps_only":
                assert r["stored_problem"] and r["expected_problem"] is None
                assert r["expected_steps"]
            elif kind == "problem_only":
                assert r["stored_problem"] is None and r["expected_problem"]
                assert r["expected_steps"] == []
            else:  # answer_only, question_only
                assert r["stored_problem"] and r["expected_problem"] is None
                assert r["expected_steps"] == []


def test_a_wrong_step_is_recorded_with_its_rule(tmp_path: Path) -> None:
    _, splits = _build(tmp_path, per_split=40, problems=200)
    wrong = [
        r
        for records in splits.values()
        for r in records
        if "wrong_step" in r["features"] and r["source"] == "generated"
    ]
    assert wrong
    for r in wrong:
        assert r["provenance"]["wrong_step"]["rule"]


def test_the_build_is_reproducible(tmp_path: Path) -> None:
    first, _ = _build(tmp_path / "a")
    second, _ = _build(tmp_path / "b")
    for split in ("dev", "test"):
        name = f"{split}/parse_input.jsonl"
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_the_report_and_the_spot_check_are_written(tmp_path: Path) -> None:
    out, _ = _build(tmp_path)
    report = json.loads((out / "review" / "parse_input_build_report.json").read_text("utf-8"))
    assert report["per_split"] == 20 and report["dev"]["n"] > 20
    assert 0 < len(_read(out / "review" / "parse_input_spotcheck.jsonl")) <= 24


def test_too_few_chains_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="usable chains"):
        build(_math_dir(tmp_path, problems=4), tmp_path / "out", per_split=20, seed=0)


def test_tidy_drops_brackets_around_one_token_only() -> None:
    assert _tidy("x = (19)") == "x = 19"
    assert _tidy("sqrt(5)") == "sqrt(5)"
    assert _tidy("2(3)") == "2(3)"
    assert _tidy("( 2^5 ) ^x") == "(2^5)^x"
    assert _tidy("(x)/(2)") == "x/2"


def test_the_hand_written_cases_are_well_formed() -> None:
    assert len(HANDWRITTEN) >= 25
    messages = [case["message"] for case in HANDWRITTEN]
    assert len(set(messages)) == len(messages)
    for case in HANDWRITTEN:
        assert case["message"].strip()
        assert all(isinstance(step, str) and step.strip() for step in case["steps"])
        if case["problem"] is None and case["stored_problem"] is None:
            assert case["steps"] == []  # nothing to attach steps to
