import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from evals import runner

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "scripts" / "eval_verify.py"
CASES = [
    {"prev": "3x + 6 = 15", "curr": "3x = 9", "relation": "equivalent", "source": "math"},
    {"prev": "3(x+2) = 15", "curr": "3x + 2 = 15", "relation": "not_valid", "source": "generated"},
    {"prev": "x = 3", "curr": "x^2 = 9", "relation": "implies", "source": "handwritten"},
    {"prev": "x = 1", "curr": "x + * 3", "relation": "unparsable", "source": "handwritten"},
    {
        "prev": "x = 9 or x = 2",
        "curr": "x = 9",
        "relation": "narrows",
        "original": "sqrt(x+7) = x-5",
        "source": "handwritten",
    },
    {
        "prev": "3x + 6 = 15",
        "curr": "3x = 9",
        "relation": "not_valid",
        "source": "generated",
    },  # wrong label
]


def _module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def test_the_node_verdict_is_compared_with_every_label() -> None:
    evaluate = _module()["evaluate"]
    metrics = evaluate(CASES)
    assert metrics["accuracy"] == 5 / 6
    assert metrics["recall/equivalent"] == 1.0
    assert metrics["recall/not_valid"] == 0.5
    assert metrics["precision/equivalent"] == 0.5
    assert metrics["support/narrows"] == 1.0
    assert metrics["confusion/not_valid->equivalent"] == 1.0
    assert metrics["accuracy/source=generated"] == 0.5
    assert metrics["n/source=handwritten"] == 3.0


def test_precision_is_left_out_for_a_relation_that_was_never_predicted() -> None:
    metrics = _module()["evaluate"](CASES[:1])
    assert "precision/equivalent" in metrics
    assert "precision/implies" not in metrics and metrics["support/implies"] == 0.0


def test_a_perfect_run_has_no_confusion_entries() -> None:
    metrics = _module()["evaluate"](CASES[:5])
    assert metrics["accuracy"] == 1.0
    assert not [name for name in metrics if name.startswith("confusion/")]


def test_the_script_writes_a_result_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "datasets" / "dev").mkdir(parents=True)
    lines = "".join(json.dumps(case) + "\n" for case in CASES[:5])
    (tmp_path / "datasets" / "dev" / "verify_steps.jsonl").write_text(lines, encoding="utf-8")
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["eval_verify.py"])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    (result,) = (tmp_path / "results" / "verify").glob("*.json")
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["split"] == "dev" and data["n_examples"] == 5
    assert data["metrics"]["accuracy"] == 1.0
    assert data["model_name"] is None and data["prompt_hash"] is None
    assert "by construction" in data["note"]


def test_a_missing_dataset_is_reported_and_nothing_is_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["eval_verify.py"])
    caplog.set_level("INFO")
    runpy.run_path(str(SCRIPT), run_name="__main__")
    assert "missing" in caplog.text and not (tmp_path / "results").exists()
