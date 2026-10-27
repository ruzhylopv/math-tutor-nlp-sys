import copy

import pytest

from tutor.nodes.localize import localize
from tutor.nodes.verify import verify
from tutor.state import Step, StepVerdict, TutorState


def _verdict(index: int, relation: str, **extra: object) -> StepVerdict:
    return StepVerdict(step_index=index, relation=relation, **extra)  # type: ignore[arg-type]


def _state(*verdicts: StepVerdict, is_correct: bool = False) -> TutorState:
    return {"step_verdicts": list(verdicts), "is_correct": is_correct}


def _result(first: int | None, focus: int | None, error_type: str | None) -> dict[str, object]:
    return {"first_error_step": first, "focus_step": focus, "error_type": error_type}


def test_the_first_not_valid_step_is_the_error() -> None:
    state = _state(_verdict(1, "equivalent"), _verdict(2, "not_valid"), _verdict(3, "not_valid"))
    assert localize(state) == _result(2, 2, "algebraic_transformation")


def test_a_not_valid_step_wins_over_a_false_justification_on_the_same_step() -> None:
    state = _state(_verdict(1, "not_valid", justification_claims_ok=False))
    assert localize(state) == _result(1, 1, "algebraic_transformation")


def test_an_unparsable_step_has_no_first_error_but_is_the_focus() -> None:
    state = _state(_verdict(1, "equivalent"), _verdict(2, "unparsable"), _verdict(3, "not_valid"))
    assert localize(state) == _result(None, 2, "other")


def test_the_order_of_the_steps_decides_between_unparsable_and_not_valid() -> None:
    state = _state(_verdict(1, "not_valid"), _verdict(2, "unparsable"))
    assert localize(state) == _result(1, 1, "algebraic_transformation")


@pytest.mark.parametrize("relation", ["equivalent", "implies", "narrows"])
def test_valid_math_with_a_false_justification_is_a_mismatch(relation: str) -> None:
    state = _state(_verdict(1, "equivalent"), _verdict(2, relation, justification_claims_ok=False))
    assert localize(state) == _result(2, 2, "reasoning_result_mismatch")


def test_a_true_or_missing_justification_is_not_an_error() -> None:
    state = _state(
        _verdict(1, "equivalent", justification_claims_ok=True),
        _verdict(2, "equivalent", justification_claims_ok=None),
        is_correct=True,
    )
    assert localize(state) == _result(None, None, None)


def test_valid_steps_with_a_wrong_answer_after_a_non_reversible_step_is_an_omission() -> None:
    state = _state(_verdict(1, "implies"), _verdict(2, "equivalent"), _verdict(3, "implies"))
    assert localize(state) == _result(None, 1, "omission_extraneous_root")


def test_valid_steps_with_a_wrong_answer_and_no_implication_is_other() -> None:
    state = _state(_verdict(1, "equivalent"), _verdict(2, "narrows"))
    assert localize(state) == _result(None, None, "other")


def test_a_correct_answer_with_nothing_flagged_has_no_error() -> None:
    state = _state(_verdict(1, "equivalent"), _verdict(2, "implies"), is_correct=True)
    assert localize(state) == _result(None, None, None)


def test_a_failed_check_line_is_information_not_an_error() -> None:
    check = _verdict(3, "equivalent", check_holds=False)
    state = _state(_verdict(1, "implies"), _verdict(2, "equivalent"), check, is_correct=True)
    assert localize(state) == _result(None, None, None)


def test_a_wrong_answer_with_no_steps_is_other() -> None:
    assert localize({}) == _result(None, None, "other")
    assert localize({"is_correct": False, "step_verdicts": []}) == _result(None, None, "other")


def test_only_the_declared_fields_are_returned_and_the_state_is_not_changed() -> None:
    state = _state(_verdict(1, "not_valid"))
    before = copy.deepcopy(state)
    assert set(localize(state)) == {"first_error_step", "focus_step", "error_type"}
    assert state == before


# --- with the real verify (assumptions about its verdicts) ---------------------------------------
def _diagnose(problem: str, *claims: str) -> dict[str, object]:
    state: TutorState = {"problem": problem, "student_steps": [Step(claim=c) for c in claims]}
    state.update(verify(state))  # type: ignore[typeddict-item]
    return localize(state)


def test_scenario_a_style_bracket_error_is_found_at_step_one() -> None:
    result = _diagnose("3(x + 2) = 15", "3x + 2 = 15", "3x = 13", "x = 13/3")
    assert result == _result(1, 1, "algebraic_transformation")


def test_squaring_without_rejecting_the_extraneous_root_is_an_omission() -> None:
    result = _diagnose(
        "sqrt(x + 7) = x - 5",
        "x + 7 = (x - 5)^2",
        "x^2 - 11x + 18 = 0",
        "x = 2 or x = 9",
    )
    assert result == _result(None, 1, "omission_extraneous_root")


def test_rejecting_the_extraneous_root_leaves_nothing_to_localize() -> None:
    result = _diagnose(
        "sqrt(x + 7) = x - 5",
        "x + 7 = (x - 5)^2",
        "x^2 - 11x + 18 = 0",
        "x = 2 or x = 9",
        "sqrt(2 + 7) = 2 - 5",
        "x = 9",
    )
    assert result == _result(None, None, None)
