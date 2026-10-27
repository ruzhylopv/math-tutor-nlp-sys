import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from evals import runner
from evals.builders.build_localize import handwritten_records

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "scripts" / "eval_localize.py"


def _module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _case(
    first: int | None,
    focus: int | None,
    error_type: str | None,
    kind: str = "k",
    source: str = "generated",
) -> dict[str, Any]:
    return {
        "problem": "2x + 3 = 11",
        "steps": [],
        "expected": {"first_error_step": first, "focus_step": focus, "error_type": error_type},
        "kind": kind,
        "source": source,
    }


def test_the_hand_written_labels_agree_with_verify_then_localize() -> None:
    """A disagreement is a bug or a wrong label; investigate, never edit the label to match."""
    module = _module()
    for _, record in handwritten_records():
        assert module["predict"](record) == module["_expected"](record), record["id"]


def test_perfect_predictions() -> None:
    cases = [_case(1, 1, "algebraic_transformation"), _case(None, None, None)]
    outcomes = [(1, 1, "algebraic_transformation"), (None, None, "none")]
    metrics = _module()["evaluate"](cases, outcomes)
    assert metrics["case_accuracy"] == metrics["error_type_accuracy"] == 1.0
    assert metrics["recall/none"] == 1.0
    assert not [name for name in metrics if name.startswith("confusion/")]


def test_each_field_is_scored_separately_and_together() -> None:
    cases = [_case(2, 2, "algebraic_transformation")] * 4
    outcomes = [
        (2, 2, "algebraic_transformation"),  # right
        (1, 2, "algebraic_transformation"),  # wrong first step
        (2, 1, "algebraic_transformation"),  # wrong focus step
        (2, 2, "other"),  # wrong type
    ]
    metrics = _module()["evaluate"](cases, outcomes)
    assert metrics["case_accuracy"] == 0.25
    assert metrics["first_error_step_accuracy"] == 0.75
    assert metrics["focus_step_accuracy"] == 0.75
    assert metrics["error_type_accuracy"] == 0.75
    assert metrics["confusion/algebraic_transformation->other"] == 1.0


def test_precision_is_left_out_for_a_type_that_was_never_predicted() -> None:
    cases = [_case(None, 1, "other")]
    metrics = _module()["evaluate"](cases, [(None, None, "none")])
    assert "precision/other" not in metrics and metrics["recall/other"] == 0.0


def test_recall_is_left_out_for_a_type_with_no_cases() -> None:
    cases = [_case(None, 1, "other")]
    metrics = _module()["evaluate"](cases, [(None, None, "none")])
    assert "recall/none" not in metrics and metrics["support/none"] == 0.0
    assert "recall/reasoning_result_mismatch" not in metrics
    assert "mismatch_detection_rate" not in metrics


def test_mismatch_detection_rate_is_the_recall_of_the_mismatch_type() -> None:
    mismatch = "reasoning_result_mismatch"
    cases = [_case(1, 1, mismatch), _case(2, 2, mismatch), _case(1, 1, "algebraic_transformation")]
    outcomes = [(1, 1, mismatch), (2, 2, "algebraic_transformation"), (1, 1, mismatch)]
    metrics = _module()["evaluate"](cases, outcomes)
    assert metrics["mismatch_detection_rate"] == 0.5
    assert metrics["precision/reasoning_result_mismatch"] == 0.5


def test_accuracy_per_kind_and_source() -> None:
    cases = [_case(1, 1, "other", "a", "generated"), _case(1, 1, "other", "b", "handwritten")]
    metrics = _module()["evaluate"](cases, [(1, 1, "other"), (2, 2, "other")])
    assert metrics["case_accuracy/kind=a"] == 1.0 and metrics["case_accuracy/kind=b"] == 0.0
    assert metrics["case_accuracy/source=handwritten"] == 0.0
    assert metrics["n/source=generated"] == 1.0
    assert metrics["case_accuracy/source=generated"] == 1.0


def test_the_script_runs_the_pipeline_and_writes_a_result_without_a_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "datasets" / "dev").mkdir(parents=True)
    records = [record for _, record in handwritten_records()][:6]
    (tmp_path / "datasets" / "dev" / "localize.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["eval_localize.py"])
    with caplog.at_level("INFO"):
        runpy.run_path(str(SCRIPT), run_name="__main__")
    (result,) = (tmp_path / "results" / "localize").glob("*.json")
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["model_name"] is None and data["n_examples"] == 6
    assert data["metrics"]["case_accuracy"] == 1.0  # the hand-written labels agree (see above)
    # the printed summary leads with the per-source accuracy
    assert "case_accuracy/source=handwritten" in caplog.text
