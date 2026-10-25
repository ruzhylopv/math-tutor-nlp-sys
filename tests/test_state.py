from typing import get_type_hints

import pytest
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from tutor.state import (
    Decision,
    LearnerProfile,
    Misconception,
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


def test_misconception_and_profile() -> None:
    assert Misconception(id="m1", description="d", topic="algebra", score=0.5).score == 0.5
    profile = LearnerProfile()
    assert profile.weak_topics == [] and profile.misconception_counts == {}


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
    assert add_messages in hints["messages"].__metadata__
