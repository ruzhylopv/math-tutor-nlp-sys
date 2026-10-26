from tutor.nodes.verify import verify
from tutor.state import Step, TutorState


def _state(problem: str, *lines: str, **claims: str) -> TutorState:
    steps = [
        Step(claim=line, justification_claim=claims.get(f"claim{i}"))
        for i, line in enumerate(lines)
    ]
    return {"problem": problem, "student_steps": steps}


def _relations(result: dict[str, object]) -> list[str]:
    return [verdict.relation for verdict in result["step_verdicts"]]  # type: ignore[attr-defined]


def test_scenario_a_turn_2_the_slip_is_step_1() -> None:
    result = verify(_state("3(x + 2) = 15", "3x + 2 = 15", "3x = 13", "x = 13/3"))
    assert _relations(result) == ["not_valid", "equivalent", "equivalent"]
    assert result["is_correct"] is False


def test_scenario_a_turn_3_a_correct_solution() -> None:
    result = verify(_state("3(x + 2) = 15", "3x + 6 = 15", "3x = 9", "x = 3"))
    assert _relations(result) == ["equivalent"] * 3
    assert result["is_correct"] is True


def test_scenario_b_turn_1_wrong_squaring() -> None:
    result = verify(
        _state(
            "sqrt(x + 7) = x - 5",
            "x + 7 = x^2 - 25",
            "x^2 - x - 32 = 0",
            "x = (1 + sqrt(129))/2 or x = (1 - sqrt(129))/2",
        )
    )
    assert _relations(result) == ["not_valid", "equivalent", "equivalent"]
    assert result["is_correct"] is False


def test_scenario_b_turn_3_squaring_implies_and_the_extraneous_root_stays() -> None:
    result = verify(
        _state(
            "sqrt(x + 7) = x - 5",
            "x + 7 = x^2 - 10x + 25",
            "x^2 - 11x + 18 = 0",
            "(x - 9)(x - 2) = 0",
            "x = 9 or x = 2",
        )
    )
    assert _relations(result) == ["implies", "equivalent", "equivalent", "equivalent"]
    assert result["is_correct"] is False  # x = 2 was never rejected


def test_scenario_b_turn_4_a_check_and_the_rejected_root_narrow_to_the_answer() -> None:
    result = verify(
        _state(
            "sqrt(x + 7) = x - 5",
            "x + 7 = x^2 - 10x + 25",
            "x^2 - 11x + 18 = 0",
            "(x - 9)(x - 2) = 0",
            "x = 9 or x = 2",
            "sqrt(9 + 7) = 9 - 5",
            "x = 9",
        )
    )
    assert _relations(result) == [
        "implies", "equivalent", "equivalent", "equivalent", "equivalent", "narrows",
    ]  # fmt: skip
    assert result["step_verdicts"][4].notes == "check line"  # type: ignore[index]
    assert result["is_correct"] is True


def test_a_wrong_justification_claim_is_flagged() -> None:
    result = verify(_state("x^2 - 11x + 18 = 0", "(x - 9)(x - 2) = 0", claim0="-2 + -9 = 11"))
    assert result["step_verdicts"][0].justification_claims_ok is False  # type: ignore[index]


def test_a_true_justification_claim_and_a_missing_one() -> None:
    result = verify(_state("x^2 - 11x + 18 = 0", "(x - 9)(x - 2) = 0", claim0="-2 + -9 = -11"))
    assert result["step_verdicts"][0].justification_claims_ok is True  # type: ignore[index]
    assert verify(_state("x = 1", "x = 1"))["step_verdicts"][0].justification_claims_ok is None  # type: ignore[index]


def test_a_problem_that_does_not_parse_is_not_compared() -> None:
    result = verify(_state("Solve the equation for x", "3x = 9", "x = 3"))
    assert _relations(result) == ["unparsable", "equivalent"]  # step 2 is compared with step 1
    assert "does not parse" in result["step_verdicts"][0].notes  # type: ignore[index]
    assert result["is_correct"] is False


def test_an_unparsable_line_does_not_become_the_next_predecessor() -> None:
    result = verify(_state("3x = 9", "three x", "x = 3"))
    assert _relations(result) == ["unparsable", "equivalent"]


def test_no_steps_is_not_correct() -> None:
    assert verify({"problem": "x = 1", "student_steps": []}) == {
        "is_correct": False,
        "step_verdicts": [],
    }
    assert verify({})["is_correct"] is False


def test_an_expression_task_is_correct_when_the_last_line_is_equivalent() -> None:
    result = verify(_state("(x + 3)^2", "x^2 + 6x + 9"))
    assert result["is_correct"] is True
    assert verify(_state("(x + 3)^2", "x^2 + 9"))["is_correct"] is False


def test_a_final_answer_without_variable_name_counts() -> None:
    assert verify(_state("3x = 9", "3"))["is_correct"] is True
