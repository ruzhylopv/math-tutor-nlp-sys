"""Orchestrator unit tests: the LLM and the learner DB are mocked or temporary."""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from tutor.config import ConfigError
from tutor.nodes import orchestrator as orch
from tutor.state import (
    Decision,
    ErrorContext,
    LearnerProfile,
    Misconception,
    MisconceptionRecord,
    Step,
    StepVerdict,
    TutorState,
)
from tutor.tools import learner_db, structured
from tutor.tools.canned_hints import NO_WORKING, canned_hint


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "learner.db")
    monkeypatch.setattr(orch, "learner_db_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def no_db_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing() -> str:
        raise ConfigError("no db")

    monkeypatch.setattr(orch, "learner_db_path", missing)


def _decide(monkeypatch: pytest.MonkeyPatch, decision: Decision | None) -> list[str]:
    seen: list[str] = []

    def fake(name: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append(text)
        return decision

    monkeypatch.setattr(structured, "call_structured", fake)
    return seen


def _mis(id_: str = "M001") -> Misconception:
    return Misconception(id=id_, description="d", topic="Algebra", score=0.9)


def _context() -> ErrorContext:
    return ErrorContext(step_number=1, before="3(x + 2) = 15", after="3x + 2 = 15")


def _msg(text: str = "hi") -> list[Any]:
    return [HumanMessage(content=text)]


STEP = [Step(claim="x = 1")]


def test_missing_stage_is_a_new_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="reply", reason="r", reply_text="Hello!"))
    out = orch.orchestrator({"messages": _msg()})
    assert out["next_action"] == "reply"
    assert out["reply_text"] == "Hello!"
    assert [m.content for m in out["messages"]] == ["Hello!"]


def test_turns_count_new_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="reply", reason="r"))
    assert orch.orchestrator({"messages": _msg(), "turns": 2})["turns"] == 3


def test_prompt_carries_message_steps_and_diagnosis_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _decide(monkeypatch, Decision(action="reply", reason="r"))
    orch.orchestrator(
        {
            "messages": _msg("why?"),
            "problem": "p",
            "student_steps": STEP,
            "error_context": _context(),
        }
    )
    assert "Student message: why?" in seen[0]
    assert "Steps found in the message: 1" in seen[0]
    assert "Diagnosis so far: yes" in seen[0]


def test_diagnose_with_steps_routes_to_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="diagnose", reason="r"))
    out = orch.orchestrator({"messages": _msg(), "problem": "p", "student_steps": STEP})
    assert out["next_action"] == "diagnose"
    assert "reply_text" not in out


def test_diagnose_without_steps_becomes_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="diagnose", reason="r"))
    out = orch.orchestrator({"messages": _msg(), "problem": "p", "student_steps": []})
    assert out["next_action"] == "ask"
    assert out["reply_text"] == orch.ASK_TEXT


def test_hint_without_diagnosis_becomes_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    out = orch.orchestrator({"messages": _msg(), "problem": "p"})
    assert out["next_action"] == "ask"


def test_question_escalates_the_hint_level(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    state: TutorState = {
        "messages": _msg("isn't it?"),
        "problem": "p",
        "topic": "Algebra",
        "error_context": _context(),
        "hint_level": 1,
    }
    out = orch.orchestrator(state)
    assert out["next_action"] == "hint"
    assert out["hint_level"] == 2
    assert out["hint_retries"] == 0


def test_question_escalation_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    state: TutorState = {
        "messages": _msg(),
        "topic": "Algebra",
        "error_context": _context(),
        "hint_level": 4,
    }
    assert orch.orchestrator(state)["hint_level"] == 4


def test_model_failure_routes_on_the_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, None)
    assert (
        orch.orchestrator({"messages": _msg(), "problem": "p", "student_steps": STEP})[
            "next_action"
        ]
        == "diagnose"
    )
    assert orch.orchestrator({"messages": _msg()})["next_action"] == "ask"


def test_a_missing_topic_does_not_wipe_the_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))  # parse_input does the real reset
    state: TutorState = {
        "messages": _msg(),
        "problem": "new",
        "topic": None,
        "error_context": _context(),
        "misconceptions_seen": ["M001"],
        "hint_level": 3,
        "hints_used": 2,
        "turns": 5,
        "step_verdicts": [StepVerdict(step_index=1, relation="not_valid")],
    }
    out = orch.orchestrator(state)
    assert out["next_action"] == "hint" and out["hint_level"] == 4 and out["turns"] == 6
    assert "error_context" not in out and "misconceptions_seen" not in out


def test_no_reset_without_an_old_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    # an `ask` turn on a new problem leaves topic None; the next turn must keep counting
    _decide(monkeypatch, Decision(action="ask", reason="r"))
    out = orch.orchestrator({"messages": _msg(), "problem": "p", "topic": None, "turns": 1})
    assert out["turns"] == 2


def test_profile_is_loaded_on_a_new_message(db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    learner_db.record_attempt(
        db, "ada", "p", "Algebra", 1, 2, 0, True, [MisconceptionRecord(misconception_id="M001")]
    )
    _decide(monkeypatch, Decision(action="ask", reason="r"))
    out = orch.orchestrator({"messages": _msg(), "student_id": "ada"})
    assert out["learner_profile"].misconception_counts == {"M001": 1}


def test_diagnosed_first_misconception_starts_at_level_one() -> None:
    out = orch.orchestrator(
        {"stage": "diagnosed", "topic": "Algebra", "misconception": _mis(), "hint_level": 3}
    )
    assert out["next_action"] == "hint"
    assert out["hint_level"] == 1
    assert out["misconceptions_seen"] == ["M001"]


def test_diagnosed_same_misconception_escalates() -> None:
    out = orch.orchestrator(
        {
            "stage": "diagnosed",
            "topic": "Algebra",
            "misconception": _mis("M001"),
            "misconceptions_seen": ["M001"],
            "hint_level": 1,
        }
    )
    assert out["hint_level"] == 2
    assert out["misconceptions_seen"] == ["M001"]


def test_diagnosed_different_misconception_resets() -> None:
    out = orch.orchestrator(
        {
            "stage": "diagnosed",
            "topic": "Algebra",
            "misconception": _mis("M002"),
            "misconceptions_seen": ["M001"],
            "hint_level": 3,
        }
    )
    assert out["hint_level"] == 1
    assert out["misconceptions_seen"] == ["M001", "M002"]


def test_diagnosed_without_misconception_escalates_only_after_a_hint() -> None:
    base: TutorState = {"stage": "diagnosed", "topic": "Algebra", "hint_level": 1}
    assert orch.orchestrator(base)["hint_level"] == 1
    assert orch.orchestrator({**base, "hints_used": 1})["hint_level"] == 2


def test_out_of_scope_topic_is_declined() -> None:
    out = orch.orchestrator({"stage": "diagnosed", "topic": "Geometry", "misconception": _mis()})
    assert out["next_action"] == "reply"
    assert out["reply_text"] == orch.OUT_OF_SCOPE_TEXT
    assert "misconceptions_seen" not in out


def _clean(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "stage": "diagnosed",
        "topic": "Algebra",
        "level": 2,
        "problem": "3(x+2)=15",
        "student_id": "ada",
        "is_correct": True,
        "step_verdicts": [StepVerdict(step_index=1, relation="equivalent")],
        "misconceptions_seen": ["M001"],
        "turns": 3,
        "hints_used": 1,
    }
    base.update(fields)
    return base  # type: ignore[return-value]


def test_clean_solution_records_the_attempt(db: str) -> None:
    out = orch.orchestrator(_clean())
    assert out["next_action"] == "reply"
    assert out["reply_text"] == orch.CORRECT_TEXT
    assert learner_db.get_profile(db, "ada").misconception_counts == {"M001": 1}
    assert out["misconceptions_seen"] == []  # the next problem starts fresh


def test_practice_is_offered_on_the_third_occurrence(db: str) -> None:
    for _ in range(2):
        learner_db.record_attempt(
            db, "ada", "p", "Algebra", 1, 2, 0, True, [MisconceptionRecord(misconception_id="M001")]
        )
    out = orch.orchestrator(_clean())
    assert "practice" in out["reply_text"]
    assert out["learner_profile"].misconception_counts["M001"] == 3


def test_no_practice_offer_on_the_second_occurrence(db: str) -> None:
    learner_db.record_attempt(
        db, "ada", "p", "Algebra", 1, 2, 0, True, [MisconceptionRecord(misconception_id="M001")]
    )
    assert "practice" not in orch.orchestrator(_clean())["reply_text"]


def test_clean_solution_without_a_db_still_replies() -> None:
    out = orch.orchestrator(_clean())
    assert out["reply_text"] == orch.CORRECT_TEXT
    assert "learner_profile" not in out


def _hinted(text: str, **fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "stage": "hinted",
        "problem": "3(x + 2) = 15",
        "error_context": _context(),
        "hint_text": text,
        "hint_level": 2,
    }
    base.update(fields)
    return base  # type: ignore[return-value]


SAFE = "What does the 3 multiply in `3(x + 2)`?"


def test_a_clean_hint_is_published() -> None:
    out = orch.orchestrator(_hinted(SAFE, hints_used=1))
    assert out["reply_text"] == SAFE
    assert out["next_action"] == "reply"
    assert out["hints_used"] == 2
    assert [m.content for m in out["messages"]] == [SAFE]
    assert isinstance(out["messages"][0], AIMessage)


def test_a_leaking_hint_is_retried_once() -> None:
    out = orch.orchestrator(_hinted("Try `3x + 6 = 15`."))
    assert out["next_action"] == "hint"
    assert out["hint_retries"] == 1
    assert "messages" not in out
    assert "hints_used" not in out


def test_a_second_leak_falls_back_to_the_canned_hint() -> None:
    out = orch.orchestrator(_hinted("Try `3x + 6 = 15`.", hint_retries=1))
    assert out["reply_text"] == canned_hint(2)
    assert out["next_action"] == "reply"
    assert out["hints_used"] == 1
    assert [m.content for m in out["messages"]] == [canned_hint(2)]


def test_an_empty_hint_counts_as_a_leak() -> None:
    assert orch.orchestrator(_hinted(""))["next_action"] == "hint"


def test_the_profile_type_is_exported() -> None:
    assert LearnerProfile().weak_topics == []


def _reply_state(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "messages": [AIMessage("What must be true of A?"), HumanMessage("it has to be zero")],
        "problem": "5A = 0",
        "topic": "Algebra",
        "intent": "answer",
        "error_context": _context(),
        "hint_level": 2,
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_a_reply_in_words_goes_to_hint_without_a_model_call_and_keeps_the_level() -> None:
    out = orch.orchestrator(_reply_state())  # a model call would fail the test (autouse guard)
    assert out["next_action"] == "hint"
    assert "hint_level" not in out and out["hint_retries"] == 0


def test_a_reply_with_a_math_line_is_checked_by_sympy() -> None:
    out = orch.orchestrator(_reply_state(student_steps=[Step(claim="A = 0")]))
    assert out["next_action"] == "diagnose"


def test_a_reply_using_a_letter_defined_earlier_goes_to_hint() -> None:
    state = _reply_state(
        problem="m^4 - 5m^2 + 4 = 0", student_steps=[Step(claim="(u - 1)(u - 4) = 0")]
    )
    out = orch.orchestrator(state)  # verify no longer knows `u`, so it would call this wrong
    assert out["next_action"] == "hint" and "hint_level" not in out


def test_a_reply_without_a_diagnosis_is_routed_by_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _decide(monkeypatch, Decision(action="ask", reason="r", reply_text="Show me."))
    out = orch.orchestrator(_reply_state(error_context=None))
    assert out["next_action"] == "ask" and len(seen) == 1


def test_the_model_sees_the_intent_and_the_tutors_last_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _decide(monkeypatch, Decision(action="ask", reason="r", reply_text="Show me."))
    orch.orchestrator(_reply_state(error_context=None, intent="stuck"))
    assert "Student intent: stuck" in seen[0]
    assert "Tutor's last message: What must be true of A?" in seen[0]


def test_the_model_sees_the_earlier_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _decide(monkeypatch, Decision(action="ask", reason="r", reply_text="Show me."))
    messages = [
        HumanMessage("Hi"),
        AIMessage("Send me a problem."),
        HumanMessage("idk where to start"),
    ]
    orch.orchestrator({"messages": messages, "problem": "2x = 4"})
    assert "Conversation so far:\nStudent: Hi\nTutor: Send me a problem." in seen[0]


def _hinted_state(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "stage": "hinted",
        "problem": "3(x + 2) = 15",
        "hint_text": "What does the 3 multiply?",
        "error_context": _context(),
        "hint_level": 1,
        "intent": "answer",
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_a_reply_that_does_not_move_forward_raises_the_next_level() -> None:
    assert orch.orchestrator(_hinted_state(reply_moves_forward=False))["hint_level"] == 2


@pytest.mark.parametrize("verdict", [True, None])
def test_a_reply_that_moves_forward_or_has_no_verdict_keeps_the_level(
    verdict: bool | None,
) -> None:
    assert "hint_level" not in orch.orchestrator(_hinted_state(reply_moves_forward=verdict))


def test_an_old_verdict_is_ignored_when_the_message_is_not_a_reply() -> None:
    out = orch.orchestrator(_hinted_state(intent="stuck", reply_moves_forward=False))
    assert "hint_level" not in out


def _diagnosed_incomplete(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "stage": "diagnosed",
        "topic": "Algebra",
        "error_type": "incomplete",
        "hint_level": 2,
        "hints_used": 1,
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_partial_progress_keeps_the_level() -> None:
    assert orch.orchestrator(_diagnosed_incomplete(intent="check_work"))["hint_level"] == 2


def test_partial_progress_raises_the_level_when_the_student_is_stuck() -> None:
    assert orch.orchestrator(_diagnosed_incomplete(intent="stuck"))["hint_level"] == 3


def test_the_first_hint_on_partial_progress_is_level_one() -> None:
    state = _diagnosed_incomplete(intent="stuck", hints_used=0)
    assert orch.orchestrator(state)["hint_level"] == 1


def _hinted_stopped(text: str, **fields: Any) -> TutorState:
    context = ErrorContext(step_number=1, before="x^2 + 4 = 5x", after="x^2 - 5x + 4 = 0")
    return _hinted(
        text, problem="x^2 + 4 = 5x", error_type="incomplete", error_context=context, **fields
    )


def test_a_stopped_solution_may_quote_its_last_valid_line() -> None:
    context = ErrorContext(step_number=1, before="3(x + 2) = 15", after="3x + 6 = 15")
    text = "Your line `3x + 6 = 15` is right. What comes next?"
    assert orch.orchestrator(_hinted(text, error_context=context))["next_action"] == "hint"
    state = _hinted(text, error_context=context, error_type="incomplete")
    assert orch.orchestrator(state)["reply_text"] == text


def test_the_line_derived_from_the_last_valid_line_is_rejected() -> None:
    out = orch.orchestrator(_hinted_stopped("Try `(x - 1)(x - 4) = 0`."))
    assert out["next_action"] == "hint" and out["hint_retries"] == 1


def test_a_second_leak_on_a_stopped_solution_uses_the_stopped_text() -> None:
    out = orch.orchestrator(_hinted_stopped("Try `(x - 1)(x - 4) = 0`.", hint_retries=1))
    assert out["reply_text"] == canned_hint(2, "incomplete")
    assert out["reply_text"] != canned_hint(2)


def _diagnosed_reply(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "stage": "diagnosed",
        "topic": "Algebra",
        "intent": "answer",
        "misconception": _mis("M001"),
        "misconceptions_seen": ["M001"],
        "hint_level": 1,
        "hints_used": 1,
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_a_wrong_math_reply_raises_the_level_only_after_its_own_hint() -> None:
    diagnosed = orch.orchestrator(_diagnosed_reply())
    assert diagnosed["next_action"] == "hint" and diagnosed["hint_level"] == 1
    hinted = _hinted_state(hint_level=diagnosed["hint_level"], reply_moves_forward=False)
    assert orch.orchestrator(hinted)["hint_level"] == 2


def test_a_math_reply_with_a_new_misconception_is_recorded_and_keeps_the_level() -> None:
    out = orch.orchestrator(_diagnosed_reply(misconception=_mis("M002"), hint_level=3))
    assert out["hint_level"] == 3
    assert out["misconceptions_seen"] == ["M001", "M002"]


def test_a_math_reply_without_a_misconception_keeps_the_level() -> None:
    assert orch.orchestrator(_diagnosed_reply(misconception=None, hint_level=2))["hint_level"] == 2


def test_routing_to_a_diagnosis_sets_the_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="diagnose", reason="r"))
    out = orch.orchestrator({"messages": _msg(), "problem": "p", "student_steps": STEP})
    assert out["next_action"] == "diagnose" and out["stage"] == "diagnosed"


def test_a_diagnosis_stores_the_focus_step_for_the_hint() -> None:
    state: TutorState = {
        "stage": "diagnosed",
        "topic": "Algebra",
        "problem": "3(x + 2) = 15",
        "student_steps": [Step(claim="3x + 2 = 15")],
        "focus_step": 1,
    }
    context = orch.orchestrator(state)["error_context"]
    assert context == ErrorContext(step_number=1, before="3(x + 2) = 15", after="3x + 2 = 15")


def test_an_out_of_scope_problem_leaves_nothing_to_hint_about() -> None:
    state: TutorState = {"stage": "diagnosed", "topic": "Geometry", "error_context": _context()}
    assert orch.orchestrator(state)["error_context"] is None


def _no_working(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "messages": [HumanMessage("idk where to start")],
        "problem": "2x + 1 = 7",
        "topic": "Algebra",
        "intent": "stuck",
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_a_stuck_student_with_no_working_can_get_a_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    out = orch.orchestrator(_no_working(hint_level=3))
    assert out["next_action"] == "hint" and out["hint_level"] == 1


def test_a_second_request_for_help_escalates(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    out = orch.orchestrator(_no_working(hint_level=1, hints_used=1))
    assert out["hint_level"] == 2


def test_no_problem_means_no_hint_for_a_stuck_student(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    assert orch.orchestrator(_no_working(problem=""))["next_action"] == "ask"


def test_a_stuck_student_on_an_out_of_scope_subject_is_declined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    out = orch.orchestrator(_no_working(topic="Geometry"))
    assert out["next_action"] == "reply" and out["reply_text"] == orch.OUT_OF_SCOPE_TEXT


def test_a_reply_to_a_no_working_hint_is_routed_by_code() -> None:
    out = orch.orchestrator(_no_working(intent="answer", hints_used=1, hint_level=2))
    assert out["next_action"] == "hint" and "hint_level" not in out


def test_a_leaking_no_working_hint_falls_back_to_its_own_canned_text() -> None:
    state = _no_working(stage="hinted", hint_retries=1, hint_text="So `x = 3` works.")
    out = orch.orchestrator(state)
    assert out["reply_text"] == canned_hint(1, NO_WORKING)


def test_handing_over_the_problem_is_routed_by_the_model_and_can_get_a_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _decide(monkeypatch, Decision(action="hint", reason="r"))
    out = orch.orchestrator(_no_working(intent="answer"))
    assert len(seen) == 1 and out["next_action"] == "hint" and out["hint_level"] == 1


def test_a_clarifying_question_with_no_working_keeps_the_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    out = orch.orchestrator(_no_working(intent="explain", hint_level=2, hints_used=2))
    assert out["next_action"] == "hint" and out["hint_level"] == 2


def test_a_clarifying_question_after_a_diagnosis_still_escalates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    state = _no_working(intent="explain", hint_level=2, hints_used=2, error_context=_context())
    assert orch.orchestrator(state)["hint_level"] == 3


def test_a_no_working_hint_listing_every_solution_is_rejected() -> None:
    state = _no_working(
        stage="hinted",
        problem="x^2 - 5x + 6 = 0",
        hint_text="Try `1` and `6`, or `2` and `3`.",
    )
    assert orch.orchestrator(state) == {"next_action": "hint", "hint_retries": 1}
