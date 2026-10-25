from typing import Any

import pytest

from tutor import graph as graph_module
from tutor.graph import build_diagnosis_graph, route_after_verify
from tutor.state import StepVerdict, TutorState
from tutor.tools.diagnosis import is_clean_solution


def _state(*verdicts: StepVerdict, is_correct: bool = True) -> TutorState:
    return {"is_correct": is_correct, "step_verdicts": list(verdicts)}


def _visited(state: TutorState) -> list[str]:
    """Names of the nodes the subgraph ran, in order."""
    graph = build_diagnosis_graph()
    return [name for update in graph.stream(state, stream_mode="updates") for name in update]


def test_clean_solution_needs_a_correct_answer() -> None:
    assert is_clean_solution(_state(StepVerdict(step_index=1, relation="equivalent")))
    assert not is_clean_solution(_state(is_correct=False))
    assert not is_clean_solution({})


def test_with_no_steps_the_answer_alone_decides() -> None:
    assert is_clean_solution(_state(is_correct=True))


def test_implication_counts_as_valid() -> None:
    assert is_clean_solution(_state(StepVerdict(step_index=1, relation="implies")))


def test_invalid_and_unparsable_steps_are_not_clean() -> None:
    assert not is_clean_solution(_state(StepVerdict(step_index=1, relation="not_valid")))
    assert not is_clean_solution(_state(StepVerdict(step_index=1, relation="unparsable")))


def test_a_flagged_justification_is_not_clean() -> None:
    flagged = StepVerdict(step_index=2, relation="equivalent", justification_claims_ok=False)
    assert not is_clean_solution(_state(flagged))
    unknown = StepVerdict(step_index=2, relation="equivalent", justification_claims_ok=None)
    assert is_clean_solution(_state(unknown))


def test_routing_after_verify() -> None:
    clean = _state(StepVerdict(step_index=1, relation="equivalent"))
    assert route_after_verify(clean) == "finish_diagnosis"
    assert route_after_verify(_state(is_correct=False)) == "localize"


def test_a_failing_verify_takes_the_full_path_through_localize_and_retrieve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_verify(state: TutorState) -> dict[str, Any]:
        return {"is_correct": False, "step_verdicts": []}

    monkeypatch.setattr(graph_module, "verify", failing_verify)
    assert _visited({"problem": "3(x + 2) = 15"}) == [
        "parse_input",
        "classify",
        "verify",
        "localize",
        "retrieve",
        "finish_diagnosis",
    ]


def test_a_clean_solution_short_circuits_to_finish_diagnosis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def clean_verify(state: TutorState) -> dict[str, Any]:
        return {
            "is_correct": True,
            "step_verdicts": [StepVerdict(step_index=1, relation="equivalent")],
        }

    monkeypatch.setattr(graph_module, "verify", clean_verify)
    assert _visited({"problem": "x + 1 = 2"}) == [
        "parse_input",
        "classify",
        "verify",
        "finish_diagnosis",
    ]
