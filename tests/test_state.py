from typing import get_args, get_type_hints

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from tutor.state import (
    Action,
    Decision,
    ErrorType,
    LearnerProfile,
    Misconception,
    Stage,
    Step,
    StepVerdict,
    TutorState,
)


def test_step_defaults() -> None:
    step = Step(claim="3x + 6 = 15")
    assert step.justification == ""
    assert step.justification_claim is None
    assert step.operation == "other"


def test_step_rejects_unknown_operation() -> None:
    with pytest.raises(ValidationError):
        Step(claim="x = 1", operation="integrate")  # type: ignore[arg-type]


def test_step_verdict_is_one_based() -> None:
    assert StepVerdict(step_index=1, relation="implies").justification_claims_ok is None
    with pytest.raises(ValidationError):
        StepVerdict(step_index=0, relation="equivalent")


def test_step_verdict_rejects_unknown_relation() -> None:
    with pytest.raises(ValidationError):
        StepVerdict(step_index=1, relation="maybe")  # type: ignore[arg-type]


def test_decision_accepts_only_known_actions() -> None:
    assert Decision(action="ask", reason="no steps given").reply_text is None
    with pytest.raises(ValidationError):
        Decision(action="solve", reason="x")  # type: ignore[arg-type]


def test_step_keeps_a_populated_justification_claim() -> None:
    step = Step(claim="x = 9", justification="add to 11", justification_claim="-2 + -9 = 11")
    assert step.justification_claim == "-2 + -9 = 11"


def test_decision_keeps_a_reply_text() -> None:
    decision = Decision(action="reply", reason="solved", reply_text="Well done")
    assert decision.reply_text == "Well done"


def test_misconception_requires_all_fields() -> None:
    with pytest.raises(ValidationError):
        Misconception(id="m1", description="d", topic="algebra")  # type: ignore[call-arg]


def test_learner_profile_defaults_are_not_shared() -> None:
    first, second = LearnerProfile(), LearnerProfile()
    first.weak_topics.append("fractions")
    first.misconception_counts["m1"] = 2
    assert second.weak_topics == [] and second.misconception_counts == {}


def test_state_has_the_designed_fields() -> None:
    hints = get_type_hints(TutorState, include_extras=True)
    expected = {
        "messages", "student_id", "problem", "student_steps", "topic", "level", "is_correct",
        "step_verdicts", "first_error_step", "focus_step", "error_type",
        "misconception_candidates", "misconception", "hint_level", "hint_text", "hint_retries",
        "stage", "next_action", "reply_text", "turns", "hints_used", "misconceptions_seen",
        "learner_profile",
    }  # fmt: skip
    assert set(hints) == expected


def test_messages_use_the_add_messages_reducer() -> None:
    hints = get_type_hints(TutorState, include_extras=True)
    reducer = hints["messages"].__metadata__[0]
    assert reducer is add_messages
    merged = reducer([HumanMessage("a")], [AIMessage("b")])
    assert [message.content for message in merged] == ["a", "b"]


def test_field_types_follow_the_design() -> None:
    hints = get_type_hints(TutorState, include_extras=True)
    assert hints["error_type"] == ErrorType
    assert hints["stage"] == Stage
    assert hints["next_action"] == Action
    assert hints["first_error_step"] == int | None
    assert hints["focus_step"] == int | None


def test_literals_match_the_architecture() -> None:
    assert get_args(Stage) == ("new_message", "diagnosed", "hinted")
    assert get_args(Action) == ("ask", "diagnose", "hint", "reply")
    # final_answer_only is not a localize output (docs/architecture.md)
    assert "final_answer_only" not in get_args(ErrorType)
