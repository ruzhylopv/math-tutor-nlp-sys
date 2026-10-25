from tutor.graph import build_diagnosis_graph, route_after_verify
from tutor.state import StepVerdict, TutorState
from tutor.tools.diagnosis import is_clean_solution


def _state(*verdicts: StepVerdict, is_correct: bool = True) -> TutorState:
    return {"is_correct": is_correct, "step_verdicts": list(verdicts)}


def test_clean_solution_needs_a_correct_answer() -> None:
    assert is_clean_solution(_state(StepVerdict(step_index=1, relation="equivalent")))
    assert not is_clean_solution(_state(is_correct=False))
    assert not is_clean_solution({})


def test_implication_counts_as_valid() -> None:
    assert is_clean_solution(_state(StepVerdict(step_index=1, relation="implies")))


def test_invalid_or_unparsable_steps_are_not_clean() -> None:
    for relation in ("not_valid", "unparsable"):
        verdict = StepVerdict(step_index=1, relation=relation)  # type: ignore[arg-type]
        assert not is_clean_solution(_state(verdict))


def test_a_flagged_justification_is_not_clean() -> None:
    flagged = StepVerdict(step_index=2, relation="equivalent", justification_claims_ok=False)
    assert not is_clean_solution(_state(flagged))
    unknown = StepVerdict(step_index=2, relation="equivalent", justification_claims_ok=None)
    assert is_clean_solution(_state(unknown))


def test_routing_after_verify() -> None:
    clean = _state(StepVerdict(step_index=1, relation="equivalent"))
    assert route_after_verify(clean) == "finish_diagnosis"
    assert route_after_verify(_state(is_correct=False)) == "localize"


def test_diagnosis_graph_runs_the_full_path_with_the_stubs() -> None:
    result = build_diagnosis_graph().invoke({"problem": "3(x + 2) = 15"})
    assert result["stage"] == "diagnosed"
    assert result["error_type"] == "algebraic_transformation"  # went through localize
    assert result["is_correct"] is False


def test_diagnosis_graph_has_the_designed_nodes() -> None:
    nodes = set(build_diagnosis_graph().get_graph().nodes)
    assert nodes >= {
        "parse_input", "classify", "verify", "localize", "retrieve", "finish_diagnosis",
    }  # fmt: skip
