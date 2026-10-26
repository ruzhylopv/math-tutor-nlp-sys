import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from evals import runner
from tutor.state import Classification
from tutor.tools import structured

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "scripts" / "eval_classify.py"


def _module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _case(subject: str, level: int) -> dict[str, Any]:
    return {"subject": subject, "level": level, "problem": f"{subject} {level}"}


def test_perfect_predictions() -> None:
    cases = [_case("Algebra", 2), _case("Geometry", 3)]
    metrics = _module()["evaluate"](cases, [("Algebra", 2), ("Geometry", 3)])
    assert metrics["topic_accuracy"] == metrics["topic_macro_f1"] == 1.0
    assert metrics["level_accuracy"] == metrics["level_within_one"] == 1.0
    assert metrics["failure_rate"] == 0.0
    assert not [name for name in metrics if name.startswith("confusion/")]


def test_macro_f1_is_the_mean_of_the_per_class_f1() -> None:
    cases = [_case("Algebra", 1), _case("Algebra", 1), _case("Geometry", 1)]
    metrics = _module()["evaluate"](cases, [("Algebra", 1), ("Geometry", 1), ("Geometry", 1)])
    # both classes: P and R are 1 and 1/2
    assert metrics["topic_macro_f1"] == pytest.approx(2 / 3)
    assert metrics["topic_accuracy"] == pytest.approx(2 / 3)
    assert metrics["confusion/Algebra->Geometry"] == 1.0


def test_in_scope_accuracy_only_counts_the_scope_boundary() -> None:
    cases = [_case("Algebra", 2), _case("Algebra", 2), _case("Geometry", 2)]
    predictions = [("Prealgebra", 2), ("Geometry", 2), ("Geometry", 2)]
    metrics = _module()["evaluate"](cases, predictions)
    assert metrics["topic_accuracy"] == pytest.approx(1 / 3)
    # Algebra->Prealgebra stays in scope
    assert metrics["in_scope_accuracy"] == pytest.approx(2 / 3)


def test_a_failed_call_on_an_out_of_scope_problem_is_not_in_scope_correct() -> None:
    metrics = _module()["evaluate"](
        [_case("Geometry", 2), _case("Geometry", 2)], [(None, None), ("Geometry", 2)]
    )
    assert metrics["in_scope_accuracy"] == 0.5


def test_level_within_one() -> None:
    cases = [_case("Algebra", 3)] * 3
    metrics = _module()["evaluate"](cases, [("Algebra", 3), ("Algebra", 4), ("Algebra", 5)])
    assert metrics["level_accuracy"] == pytest.approx(1 / 3)
    assert metrics["level_within_one"] == pytest.approx(2 / 3)


def test_a_failed_call_is_wrong_everywhere_and_counted() -> None:
    metrics = _module()["evaluate"](
        [_case("Algebra", 2), _case("Algebra", 2)], [(None, None), ("Algebra", 2)]
    )
    assert metrics["failure_rate"] == 0.5 and metrics["topic_accuracy"] == 0.5
    assert metrics["level_accuracy"] == 0.5 and metrics["level_within_one"] == 0.5
    assert metrics["confusion/Algebra->(failed)"] == 1.0
    assert metrics["recall/Algebra"] == 0.5


def test_the_script_runs_the_node_and_writes_a_result_with_the_model_and_the_prompt_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "datasets" / "dev").mkdir(parents=True)
    cases = [
        {"id": "a", "problem": "Solve 3x = 9.", "subject": "Algebra", "level": 1},
        {"id": "b", "problem": "Find the area.", "subject": "Geometry", "level": 2},
    ]
    (tmp_path / "datasets" / "dev" / "classify.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8"
    )
    answers = {"Solve 3x = 9.": Classification(topic="Algebra", level=1)}

    def fake(prompt: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        return answers.get(text)  # the second problem gets None: a failed call

    monkeypatch.setattr(structured, "call_structured", fake)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "some/model")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["eval_classify.py"])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    (result,) = (tmp_path / "results" / "classify").glob("*.json")
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["model_name"] == "some/model" and data["prompt_hash"]
    assert data["n_examples"] == 2 and data["metrics"]["topic_accuracy"] == 0.5
    assert data["metrics"]["failure_rate"] == 0.5 and "MATH" in data["note"]
