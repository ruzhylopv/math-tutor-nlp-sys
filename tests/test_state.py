from typing import get_args, get_type_hints

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from tutor.state import (
    Action,
    Decision,
    ErrorType,
    HintText,
    Intent,
    LearnerProfile,
    Misconception,
    Operation,
    ParsedInput,
    Relation,
    Stage,
    Step,
    StepKind,
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


def test_step_verdict_check_result_defaults_to_none() -> None:
    assert StepVerdict(step_index=1, relation="equivalent").check_holds is None


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
        "messages", "student_id", "problem", "student_steps", "intent", "topic", "level",
        "is_correct", "step_verdicts", "first_error_step", "focus_step", "error_context",
        "error_type", "misconception_candidates", "misconception", "hint_level", "hint_text",
        "reply_moves_forward", "hint_retries",
        "stage", "next_action", "decision_reason", "reply_text", "turns", "hints_used",
        "misconceptions_seen",
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
    assert hints["error_type"] == ErrorType | None
    assert hints["stage"] == Stage
    assert hints["next_action"] == Action
    assert hints["first_error_step"] == int | None
    assert hints["focus_step"] == int | None
    assert hints["level"] == int | None  # None until parse_input gets one for the problem


def test_literals_match_the_architecture() -> None:
    assert get_args(Stage) == ("new_message", "diagnosed", "hinted")
    assert get_args(Action) == ("ask", "diagnose", "hint", "reply")
    assert get_args(Relation) == (
        "equivalent", "implies", "narrows", "not_valid", "unparsable",
    )  # fmt: skip
    assert get_args(Operation) == (
        "expand", "rearrange", "factor", "zero-product", "substitute", "square", "other",
    )  # fmt: skip
    assert "other" in get_args(ErrorType)  # the fallback added in M4a
    # final_answer_only is not a localize output (docs/architecture.md)
    assert "final_answer_only" not in get_args(ErrorType)


def test_parsed_input_defaults_to_no_problem_and_no_steps() -> None:
    parsed = ParsedInput()
    assert parsed.problem is None and parsed.steps == []


def test_step_kind_defaults_to_equation() -> None:
    assert Step(claim="x = 1").kind == "equation"  # old checkpoints and datasets have no kind
    assert get_args(StepKind) == ("equation", "definition", "reason", "check", "other")
    with pytest.raises(ValidationError):
        Step(claim="x = 1", kind="sentence")  # type: ignore[arg-type]


def test_parsed_input_carries_intent_and_classification() -> None:
    parsed = ParsedInput()
    assert (parsed.intent, parsed.topic, parsed.level) == ("other", None, None)
    assert "answer" in get_args(Intent)
    assert ParsedInput(intent="answer", topic="Algebra", level=2).level == 2
    with pytest.raises(ValidationError):
        ParsedInput(level=6)


def test_incomplete_is_an_error_type() -> None:
    assert "incomplete" in get_args(ErrorType)


def test_hint_reply_verdict_defaults_to_none() -> None:
    assert HintText(text="What next?").reply_moves_forward is None
    assert HintText(text="Yes!", reply_moves_forward=True).reply_moves_forward is True


def test_parsed_level_starts_at_one() -> None:
    assert ParsedInput(topic="Algebra", level=1).level == 1
    with pytest.raises(ValidationError):
        ParsedInput(topic="Algebra", level=0)
