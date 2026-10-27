import runpy
from pathlib import Path
from typing import Any

import pytest

from tutor.state import HintRubric
from tutor.tools.canned_hints import canned_hint

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "scripts" / "eval_hint.py"


def _module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _rubric(**changes: bool) -> HintRubric:
    base = {
        "praises_correct_work": True,
        "socratic": True,
        "on_target": True,
        "fits_level": True,
        "reveals_answer": False,
    }
    return HintRubric(**(base | changes))


def _result(
    level: int = 1,
    leaks: list[str] | None = None,
    judge: HintRubric | None = None,
    canned: bool = False,
    available: bool = False,
    used: bool = False,
) -> dict[str, Any]:
    return {
        "id": f"c{level}",
        "level": level,
        "leaks": leaks or [],
        "judge": judge,
        "canned": canned,
        "counterexample_available": available,
        "counterexample_used": used,
    }


def _case(identifier: str, level: int) -> dict[str, Any]:
    return {"id": identifier, "level": level}


def test_leakage_and_judge_rates() -> None:
    results = [
        _result(1, judge=_rubric()),
        _result(2, leaks=["states the answer: x = 3"], judge=_rubric(reveals_answer=True)),
        _result(2, judge=_rubric(socratic=False)),
        _result(3, judge=_rubric(on_target=False)),
    ]
    metrics = _module()["evaluate"](results)
    assert metrics["leakage_rate"] == 0.25
    assert metrics["leakage_rate/level=2"] == 0.5
    assert metrics["judge_reveals_answer_rate"] == 0.25
    assert metrics["judge_socratic"] == 0.75 and metrics["judge_on_target"] == 0.75
    assert metrics["judge_fits_level/level=2"] == 1.0
    assert metrics["n"] == 4.0 and metrics["n/level=4"] == 0.0


def test_a_failed_judge_is_counted_and_left_out_of_the_pass_rates() -> None:
    results = [_result(judge=_rubric()), _result(judge=None)]
    metrics = _module()["evaluate"](results)
    assert metrics["judge_failure_rate"] == 0.5
    assert metrics["judge_socratic"] == 1.0


def test_counterexample_use_counts_only_levels_where_numbers_were_available() -> None:
    results = [
        _result(2, judge=_rubric(), available=True, used=True),
        _result(2, judge=_rubric(), available=True, used=False),
        _result(2, judge=_rubric(), available=False),
        _result(1, judge=_rubric()),
    ]
    metrics = _module()["evaluate"](results)
    assert metrics["counterexample_use_rate"] == 0.5
    assert metrics["n/counterexample_available"] == 2.0


def test_no_judgements_at_all_does_not_divide_by_zero() -> None:
    metrics = _module()["evaluate"]([_result(judge=None)])
    assert metrics["judge_socratic"] == 0.0 and metrics["judge_failure_rate"] == 1.0


def test_the_limit_takes_cases_in_turn_over_the_levels() -> None:
    cases = [_case(f"c{n}", 1 + n % 4) for n in range(40)]
    chosen = _module()["sample_by_level"](cases, 8)
    assert sorted(case["level"] for case in chosen) == [1, 1, 2, 2, 3, 3, 4, 4]
    assert chosen == _module()["sample_by_level"](list(reversed(cases)), 8)


def test_a_limit_above_the_size_returns_all() -> None:
    cases = [_case(f"c{n}", 1 + n % 4) for n in range(6)]
    assert len(_module()["sample_by_level"](cases, 99)) == 6


def test_the_human_sample_is_capped_and_has_blank_human_fields() -> None:
    results = [
        {**_result(1 + n % 4, judge=_rubric()), "id": f"c{n}", "hint_text": "h",
         "wrong_line": "w", "before": "b"}
        for n in range(30)
    ]  # fmt: skip
    rows = _module()["sample_rows"](results)
    assert len(rows) == 20
    assert all(row["human_ok"] is None and row["human_note"] == "" for row in rows)
    assert rows[0]["judge"]["socratic"] is True


def _real_case() -> dict[str, Any]:
    return {
        "id": "gen/M001#0",
        "problem": "12 - (-5)",
        "steps": [{"claim": "12 - 5", "justification": ""}],
        "focus_step": 1,
        "error_type": "algebraic_transformation",
        "topic": "Prealgebra",
        "expected": "M001",
        "source": "generated",
        "level": 2,
    }


def test_the_state_is_built_like_the_graph_builds_it() -> None:
    state, context, misconception = _module()["build_state"](_real_case())
    assert (context.before, context.after, context.step_number) == ("12 - (-5)", "12 - 5", 1)
    assert state["error_context"] == context and state["hint_level"] == 2
    assert misconception.id == "M001" and misconception.score == 1.0


def test_run_case_grades_the_hint_with_the_automatic_check_and_the_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    run_case = module["run_case"]
    from tutor.state import HintText
    from tutor.tools import structured

    def fake(name: str, schema: type, text: str, retries: int = 1) -> Any:
        return HintText(text="Try 12 - 5 and 12 + 5 with numbers.") if name == "hint" else _rubric()

    monkeypatch.setattr(structured, "call_structured", fake)
    result = run_case(_real_case())
    assert result["hint_text"].startswith("Try")
    assert result["leaks"] == [] and result["canned"] is False
    assert result["judge"] == _rubric()


def test_a_failed_hint_call_counts_as_canned(monkeypatch: pytest.MonkeyPatch) -> None:
    from tutor.tools import structured

    monkeypatch.setattr(structured, "call_structured", lambda *args, **kwargs: None)
    result = _module()["run_case"](_real_case())
    assert result["canned"] is True and result["hint_text"] == canned_hint(2)
    assert result["judge"] is None
