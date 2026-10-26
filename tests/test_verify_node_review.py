"""Regression tests for the node problems found by the M2 review: scenario B, checks, chains."""

from tutor.nodes.verify import verify
from tutor.state import Step, StepVerdict, TutorState

PROBLEM_B = "sqrt(x + 7) = x - 5"


def _run(problem: str, *lines: str) -> tuple[bool, list[StepVerdict]]:
    state: TutorState = {"problem": problem, "student_steps": [Step(claim=line) for line in lines]}
    result = verify(state)
    return bool(result["is_correct"]), list(result["step_verdicts"])


def test_scenario_b_turn_1_with_the_literal_plus_minus_line() -> None:
    correct, verdicts = _run(
        PROBLEM_B, "x + 7 = x^2 - 25", "x^2 - x - 32 = 0", "x = (1 +- sqrt(129))/2"
    )
    assert [v.relation for v in verdicts] == ["not_valid", "equivalent", "equivalent"]
    assert correct is False


def test_a_plus_minus_answer_can_be_right() -> None:
    correct, verdicts = _run("x^2 = 4", "x = +-2")
    assert [v.relation for v in verdicts] == ["equivalent"]
    assert correct is True


def test_scenario_b_turn_4_a_failing_check_is_not_an_error() -> None:
    correct, verdicts = _run(
        PROBLEM_B,
        "x + 7 = x^2 - 10x + 25",
        "x^2 - 11x + 18 = 0",
        "(x - 9)(x - 2) = 0",
        "x = 9 or x = 2",
        "sqrt(2 + 7) = 2 - 5",  # the check that rejects x = 2: false, and that is the point
        "x = 9",
    )
    assert [v.relation for v in verdicts] == [
        "implies", "equivalent", "equivalent", "equivalent", "equivalent", "narrows",
    ]  # fmt: skip
    check = verdicts[4]
    assert check.notes == "check line" and check.check_holds is False
    assert correct is True


def test_a_check_line_that_holds_records_it() -> None:
    _, verdicts = _run("3x = 9", "x = 3", "3 * 3 = 9")
    assert verdicts[1].check_holds is True and verdicts[1].relation == "equivalent"


def test_only_check_lines_have_a_check_result() -> None:
    _, verdicts = _run("3x = 9", "x = 3")
    assert verdicts[0].check_holds is None


def test_a_check_in_the_middle_does_not_break_the_chain() -> None:
    _, verdicts = _run("3x + 6 = 15", "3 = 3", "3x = 9", "x = 3")
    assert [v.relation for v in verdicts] == ["equivalent"] * 3  # "3x = 9" follows the problem


def test_an_unparsable_line_in_the_middle_is_skipped_as_a_predecessor() -> None:
    _, verdicts = _run("3x + 6 = 15", "3x = 9", "three x", "x = 3")
    assert [v.relation for v in verdicts] == ["equivalent", "unparsable", "equivalent"]


def test_a_wrong_line_after_a_check_is_still_caught() -> None:
    _, verdicts = _run("3x + 6 = 15", "3 = 3", "3x = 21")
    assert verdicts[1].relation == "not_valid"
