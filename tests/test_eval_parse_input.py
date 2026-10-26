import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from evals import runner
from tutor.state import ParsedInput, Step
from tutor.tools import structured

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "scripts" / "eval_parse_input.py"


def _module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _case(
    problem: str | None, steps: list[str], features: tuple[str, ...] = (), source: str = "generated"
) -> dict[str, Any]:
    return {
        "message": "m",
        "stored_problem": None,
        "expected_problem": problem,
        "expected_steps": steps,
        "features": list(features),
        "source": source,
    }


def test_norm_and_canon() -> None:
    module = _module()
    assert module["norm"]("x  =  (19). ") == "x=(19)"
    assert module["canon"]("x = (19)") == module["canon"]("x=19")
    assert module["canon"]("2 * x") == module["canon"]("2x")
    assert module["canon"]("sqrt(5)") == "sqrt(5)"  # a function call keeps its brackets
    assert module["canon"]("x = 3") != module["canon"]("x = 4")


def test_perfect_predictions() -> None:
    cases = [_case("2x = 4", ["x = 2"]), _case(None, [])]
    metrics = _module()["evaluate"](cases, [("2x = 4", ["x = 2"], False), (None, [], False)])
    assert metrics["case_accuracy"] == metrics["case_accuracy_strict"] == 1.0
    assert metrics["claim_recall_exact"] == 1.0 and metrics["no_working_accuracy"] == 1.0
    assert metrics["failure_rate"] == metrics["invented_steps_rate"] == 0.0


def test_a_corrected_step_is_not_faithful() -> None:
    cases = [_case("5x - 4 = 11", ["5x = 7", "x = 7/5"])]
    metrics = _module()["evaluate"](cases, [("5x - 4 = 11", ["5x = 15", "x = 3"], False)])
    assert metrics["problem_accuracy"] == 1.0
    assert metrics["steps_accuracy"] == 0.0 and metrics["case_accuracy"] == 0.0
    assert metrics["claim_recall_exact"] == 0.0


def test_formatting_differences_pass_canonical_but_not_strict() -> None:
    cases = [_case("2x = 4", ["x = (2)"])]
    metrics = _module()["evaluate"](cases, [("2x = 4", ["x = 2"], False)])
    assert metrics["case_accuracy"] == 1.0 and metrics["case_accuracy_strict"] == 0.0


def test_a_restated_problem_when_none_was_expected_is_wrong() -> None:
    metrics = _module()["evaluate"]([_case(None, ["x = 2"])], [("2x = 4", ["x = 2"], False)])
    assert metrics["problem_accuracy"] == 0.0 and metrics["steps_accuracy"] == 1.0


def test_invented_and_dropped_steps_are_counted() -> None:
    cases = [_case(None, ["a = 1"]), _case(None, ["a = 1", "b = 2"]), _case(None, [])]
    predictions = [
        (None, ["a = 1", "c = 3"], False),
        (None, ["a = 1"], False),
        (None, ["z = 1"], False),
    ]
    metrics = _module()["evaluate"](cases, predictions)
    assert metrics["invented_steps_rate"] == pytest.approx(2 / 3)
    assert metrics["dropped_steps_rate"] == pytest.approx(1 / 3)
    assert metrics["no_working_accuracy"] == 0.0 and metrics["n/no_working"] == 1.0
    assert metrics["claim_recall_exact"] == pytest.approx(2 / 3)  # position-wise, 3 expected


def test_parse_rate_counts_claims_the_checker_cannot_read() -> None:
    cases = [_case(None, ["x = 2", "y"])]
    metrics = _module()["evaluate"](cases, [(None, ["x = 2", "hello world"], False)])
    assert metrics["sympy_parse_rate"] == 0.5


def test_failures_are_counted_and_the_case_is_judged_on_what_came_back() -> None:
    cases = [_case("x = 1", ["x = 1"]), _case(None, [])]
    metrics = _module()["evaluate"](cases, [(None, [], True), (None, [], True)])
    assert metrics["failure_rate"] == 1.0 and metrics["case_accuracy"] == 0.5


def test_metrics_by_feature_and_source() -> None:
    cases = [
        _case("a = 1", ["b = 2"], ("latex",)),
        _case("a = 1", ["b = 2"], ("latex", "typos"), "handwritten"),
    ]
    metrics = _module()["evaluate"](
        cases, [("a = 1", ["b = 2"], False), ("a = 1", ["b = 3"], False)]
    )
    assert metrics["case_accuracy/feature=latex"] == 0.5 and metrics["n/feature=latex"] == 2.0
    assert metrics["case_accuracy/feature=typos"] == 0.0
    assert (
        metrics["case_accuracy/source=handwritten"] == 0.0 and metrics["n/source=generated"] == 1.0
    )


def test_the_script_runs_the_node_and_writes_a_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "datasets" / "dev").mkdir(parents=True)
    cases = [
        {**_case("2x = 4", ["x = 2"]), "id": "a", "message": "Solve 2x = 4\nx = 2"},
        {**_case(None, []), "id": "b", "message": "why?", "stored_problem": "2x = 4"},
        {**_case(None, ["y = 1"]), "id": "c", "message": "y = 1"},
    ]
    (tmp_path / "datasets" / "dev" / "parse_input.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8"
    )
    answers = {
        "Stored problem: none\n\nStudent message:\nSolve 2x = 4\nx = 2": ParsedInput(
            problem="2x = 4", steps=[Step(claim="x = 2")]
        ),
        "Stored problem: 2x = 4\n\nStudent message:\nwhy?": ParsedInput(),
    }  # the third message gets None: a failed call

    def fake(prompt: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        return answers.get(text)

    monkeypatch.setattr(structured, "call_structured", fake)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "some/model")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["eval_parse_input.py"])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    (result,) = (tmp_path / "results" / "parse_input").glob("*.json")
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["model_name"] == "some/model" and data["prompt_hash"]
    assert data["n_examples"] == 3 and data["metrics"]["case_accuracy"] == pytest.approx(2 / 3)
    assert data["metrics"]["failure_rate"] == pytest.approx(1 / 3)
