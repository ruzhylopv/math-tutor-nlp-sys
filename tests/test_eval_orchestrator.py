"""The orchestrator eval's metrics and its prediction wrapper (model scripted)."""

import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from evals.scenario_runner import ScenarioResult, TurnResult
from evals.scripts import eval_orchestrator as ev
from tutor.state import Decision
from tutor.tools import structured


def _case(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "message": "m",
        "problem": "3x = 9",
        "n_steps": 0,
        "diagnosed": False,
        "expected_action": "ask",
    }
    base.update(fields)
    return base


def test_routing_metrics() -> None:
    cases = [_case(expected_action=a) for a in ("ask", "ask", "hint", "reply")]
    metrics = ev.evaluate_routing(cases, ["ask", "diagnose", "hint", "reply"])
    assert metrics["routing_accuracy"] == 0.75
    assert metrics["recall/ask"] == 0.5
    assert metrics["support/ask"] == 2.0
    assert metrics["confusion/ask->diagnose"] == 1.0
    assert "recall/diagnose" not in metrics  # no case expects it


def test_predict_builds_the_state_and_applies_the_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(name: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append(text)
        return Decision(action="hint", reason="r")

    monkeypatch.setattr(structured, "call_structured", fake)
    assert ev.predict(_case(diagnosed=True)) == "hint"
    assert "Diagnosis so far: yes" in seen[-1]
    # a hint with no diagnosis is turned into ask by the node's guard
    assert ev.predict(_case(diagnosed=False)) == "ask"


def _turn(
    failures: list[str],
    level: int | None = None,
    leaks: list[str] | None = None,
    ok: bool | None = None,
) -> TurnResult:
    return TurnResult(
        student="s",
        visited=[],
        reply="r",
        hint_level=level,
        leaks=leaks or [],
        misconception=None,
        failures=failures,
        misconception_ok=ok,
    )


def test_scenario_metrics() -> None:
    result = ScenarioResult(
        name="A",
        turns=[
            _turn([]),
            _turn(["did not visit hint"], level=1, ok=False),
            _turn([], level=2, leaks=["x = 3"], ok=True),
            _turn([]),
        ],
    )
    metrics = ev.evaluate_scenarios([result])
    assert metrics["turn_pass_rate"] == 0.75
    assert metrics["leak_rate"] == 0.5
    assert metrics["misconception_match_rate"] == 0.5
    assert metrics["hints_given/A"] == 2.0
    assert metrics["turns_passed/A"] == 3.0


def test_routing_reports_a_missing_dataset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("evals.runner.DATASETS_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["eval_orchestrator.py"])
    caplog.set_level("INFO")
    runpy.run_path(str(Path(ev.__file__)), run_name="__main__")
    assert "missing" in caplog.text
