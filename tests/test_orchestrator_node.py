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
from tutor.tools.canned_hints import canned_hint


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


def test_new_problem_resets_the_old_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    _decide(monkeypatch, Decision(action="hint", reason="r"))
    state: TutorState = {
        "messages": _msg(),
        "problem": "new",
        "topic": None,  # parse_input cleared it
        "error_context": _context(),
        "misconceptions_seen": ["M001"],
        "hint_level": 3,
        "hints_used": 2,
        "turns": 5,
        "step_verdicts": [StepVerdict(step_index=1, relation="not_valid")],
    }
    out = orch.orchestrator(state)
    assert out["misconceptions_seen"] == []
    assert out["error_context"] is None
    assert out["hint_level"] == 1
    assert out["hints_used"] == 0
    assert out["turns"] == 1
    assert out["next_action"] == "ask"  # the old diagnosis is gone, so no hint


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
