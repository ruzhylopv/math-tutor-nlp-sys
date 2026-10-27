import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from evals import runner
from tutor.state import Misconception
from tutor.tools import retrieval

SCRIPT = Path(__file__).resolve().parents[1] / "evals" / "scripts" / "eval_retrieve.py"


def _module() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT))


def _case(expected: str, source: str = "generated", category: str = "fractions") -> dict[str, Any]:
    return {
        "problem": "1/2 + 1/3",
        "steps": [{"claim": "2/5", "justification": ""}],
        "focus_step": 1,
        "error_type": "algebraic_transformation",
        "topic": "Prealgebra",
        "expected": expected,
        "source": source,
        "category": category,
    }


def test_recall_and_map_by_rank() -> None:
    cases = [_case("A"), _case("B"), _case("C"), _case("D")]
    rankings = [["A", "x"], ["x", "B"], ["x", "y", "C"], ["x", "y", "z", "w", "v"]]
    metrics = _module()["evaluate"](cases, rankings, 100)
    assert metrics["recall@1"] == 0.25
    assert metrics["recall@3"] == 0.75
    assert metrics["recall@5"] == 0.75
    assert metrics["map@5"] == pytest.approx((1 + 1 / 2 + 1 / 3 + 0) / 4)


def test_a_right_answer_beyond_rank_five_counts_as_a_miss() -> None:
    metrics = _module()["evaluate"]([_case("G")], [["a", "b", "c", "d", "e", "G"]], 100)
    assert metrics["recall@5"] == 0.0 and metrics["map@5"] == 0.0


def test_the_random_baseline_follows_the_catalogue_size() -> None:
    metrics = _module()["evaluate"]([_case("A")], [["A"]], 100)
    assert metrics["random_recall@1"] == 0.01 and metrics["random_recall@5"] == 0.05


def test_metrics_per_source_and_category() -> None:
    cases = [_case("A", "generated", "fractions"), _case("B", "handwritten", "radicals")]
    metrics = _module()["evaluate"](cases, [["A"], ["x"]], 10)
    assert metrics["recall@1/source=generated"] == 1.0
    assert metrics["recall@1/source=handwritten"] == 0.0
    assert metrics["recall@1/category=radicals"] == 0.0 and metrics["n/category=fractions"] == 1.0


def test_predict_runs_the_node_and_returns_the_ids_best_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str, int]] = []

    def fake(previous: str, written: str, k: int = 5) -> list[Misconception]:
        seen.append((previous, written, k))
        return [
            Misconception(id=i, description="d", topic="Algebra", score=0.5) for i in ("M2", "M1")
        ]

    monkeypatch.setattr(retrieval, "search", fake)
    assert _module()["predict"](_case("M1")) == ["M2", "M1"]
    assert seen == [("1/2 + 1/3", "2/5", 5)]


def test_the_script_writes_a_result_without_a_model_or_a_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "datasets" / "dev").mkdir(parents=True)
    cases = [{**_case("M1"), "id": "a"}, {**_case("M9", "handwritten"), "id": "b"}]
    (tmp_path / "datasets" / "dev" / "retrieve.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8"
    )
    monkeypatch.setattr(
        retrieval,
        "search",
        lambda previous, written, k=5: [
            Misconception(id="M1", description="d", topic="Algebra", score=0.9)
        ],
    )
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["eval_retrieve.py"])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    (result,) = (tmp_path / "results" / "retrieve").glob("*.json")
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["n_examples"] == 2 and data["model_name"] is None
    assert data["metrics"]["recall@1"] == 0.5 and "all-MiniLM" in data["note"]


def test_abstention_counts_answers_and_their_precision() -> None:
    cases = [_case("A"), _case("B"), _case("C"), _case("D")]
    metrics = _module()["abstention"](cases, ["A", "x", None, "D"])
    assert metrics == {
        "answered_rate": 0.75,
        "answered_precision": 2 / 3,
        "recall@1_if_forced": 0.5,
    }


def test_abstention_when_nothing_is_answered() -> None:
    metrics = _module()["abstention"]([_case("A")], [None])
    assert metrics["answered_rate"] == 0.0 and metrics["answered_precision"] == 0.0
