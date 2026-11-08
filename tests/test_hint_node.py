from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from tutor.nodes.hint import hint
from tutor.state import ErrorContext, HintText, Misconception, TutorState
from tutor.tools import structured
from tutor.tools.canned_hints import MAX_LEVEL, NO_WORKING, canned_hint
from tutor.tools.catalogue import load_catalogue


@pytest.fixture
def prompts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    seen: list[tuple[str, str, str]] = []

    def fake(name: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append((name, schema.__name__, text))
        return HintText(text="  What does the 3 multiply in `3(x + 2)`?  ")

    monkeypatch.setattr(structured, "call_structured", fake)
    return seen


def _state(**fields: Any) -> TutorState:
    entry = load_catalogue()[0]
    base: dict[str, Any] = {
        "problem": "3(x + 2) = 15",
        "error_context": ErrorContext(
            step_number=2,
            before="3(x + 2) = 15",
            after="3x + 2 = 15",
            correct_steps=["3(x + 2) = 15"],
        ),
        "misconception": Misconception(
            id=entry.id, description=entry.description, topic=entry.topic, score=0.9
        ),
        "hint_level": 1,
        "student_steps": [],  # cleared by parse_input after a question: hint must not need them
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_the_model_answer_becomes_the_hint_and_the_stage_is_hinted(
    prompts: list[tuple[str, str, str]],
) -> None:
    assert hint(_state()) == {
        "hint_text": "What does the 3 multiply in `3(x + 2)`?",
        "stage": "hinted",
    }
    assert [(name, schema) for name, schema, _ in prompts] == [("hint", "HintText")]


def test_the_prompt_text_uses_the_stored_wrong_step_not_the_student_steps(
    prompts: list[tuple[str, str, str]],
) -> None:
    hint(_state())
    text = prompts[0][2]
    assert "Hint level: 1" in text
    assert "Line before the wrong step: 3(x + 2) = 15" in text
    assert "The student's wrong line: 3x + 2 = 15" in text
    assert "Earlier lines that are correct: 3(x + 2) = 15" in text
    assert load_catalogue()[0].description in text


def test_level_1_gets_no_counterexample_and_no_rule(prompts: list[tuple[str, str, str]]) -> None:
    hint(_state(hint_level=1))
    assert "Counterexample" not in prompts[0][2] and "General rule" not in prompts[0][2]


def test_level_2_gets_the_numbers_from_sympy(prompts: list[tuple[str, str, str]]) -> None:
    hint(_state(hint_level=2))
    assert (
        "With x = 2, the left side is 12 in the line before and 8 in the student's line."
        in (prompts[0][2])
    )


def test_level_2_without_a_counterexample_says_so(prompts: list[tuple[str, str, str]]) -> None:
    context = ErrorContext(step_number=1, before="x > 1", after="x > 2")
    hint(_state(hint_level=2, error_context=context))
    assert "Counterexample: none available" in prompts[0][2]


def test_only_level_4_gets_the_general_rule(prompts: list[tuple[str, str, str]]) -> None:
    rule = load_catalogue()[0].correct_rule
    hint(_state(hint_level=3))
    hint(_state(hint_level=4))
    assert rule not in prompts[0][2]
    assert f"General rule you may state: {rule}" in prompts[1][2]


def test_without_a_misconception_the_prompt_says_unknown_and_has_no_rule(
    prompts: list[tuple[str, str, str]],
) -> None:
    hint(_state(hint_level=4, misconception=None))
    assert "Misconception: unknown" in prompts[0][2] and "General rule" not in prompts[0][2]


@pytest.mark.parametrize(("given", "used"), [(0, 1), (-2, 1), (9, MAX_LEVEL)])
def test_the_level_is_clamped(given: int, used: int, prompts: list[tuple[str, str, str]]) -> None:
    hint(_state(hint_level=given))
    assert f"Hint level: {used}" in prompts[0][2]


def test_a_missing_level_means_level_1(prompts: list[tuple[str, str, str]]) -> None:
    state = _state()
    del state["hint_level"]
    hint(state)
    assert "Hint level: 1" in prompts[0][2]


def test_without_an_error_context_the_canned_hint_is_used_and_the_model_is_not_called() -> None:
    state = _state(hint_level=3)
    del state["error_context"]
    assert hint(state) == {"hint_text": canned_hint(3), "stage": "hinted"}


@pytest.mark.parametrize("answer", [None, HintText(text="   ")])
def test_a_failed_or_blank_model_answer_gives_the_canned_hint(
    answer: HintText | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(structured, "call_structured", lambda *a, **k: answer)
    assert hint(_state(hint_level=2))["hint_text"] == canned_hint(2)


def test_the_node_returns_only_its_declared_fields(prompts: list[tuple[str, str, str]]) -> None:
    assert set(hint(_state())) == {"hint_text", "stage"}


def _stopped(**fields: Any) -> TutorState:
    context = ErrorContext(
        step_number=2, before="2x + 6 = 14", after="2x = 8", correct_steps=["2x + 6 = 14"]
    )
    return _state(error_type="incomplete", error_context=context, misconception=None, **fields)


def test_a_stopped_solution_is_never_described_as_wrong(
    prompts: list[tuple[str, str, str]],
) -> None:
    hint(_stopped(hint_level=2, problem="2(x + 3) = 14"))
    text = prompts[0][2]
    assert "every line so far is correct" in text
    assert "The student's last valid line: 2x = 8" in text
    assert "wrong" not in text and "Counterexample" not in text


@pytest.mark.parametrize(("intent", "said"), [("stuck", "yes"), ("check_work", "no")])
def test_the_hint_for_a_stopped_solution_knows_if_the_student_is_stuck(
    prompts: list[tuple[str, str, str]], intent: str, said: str
) -> None:
    hint(_stopped(intent=intent))
    assert f"Student says they are stuck: {said}" in prompts[0][2]


def _replying(**fields: Any) -> TutorState:
    messages = [
        HumanMessage("my work"),
        AIMessage("What must be true of A?"),
        HumanMessage("  it has to be zero "),
    ]
    return _state(intent="answer", messages=messages, **fields)


def _answer_with(monkeypatch: pytest.MonkeyPatch, answer: HintText | None) -> None:
    monkeypatch.setattr(structured, "call_structured", lambda name, schema, text, retries=1: answer)


def test_a_reply_gives_the_model_the_question_and_the_reply(
    prompts: list[tuple[str, str, str]],
) -> None:
    hint(_replying())
    assert "Tutor's last message: What must be true of A?" in prompts[0][2]
    assert "Student's reply: it has to be zero" in prompts[0][2]


@pytest.mark.parametrize("verdict", [True, False, None])
def test_the_verdict_on_a_reply_is_returned(
    monkeypatch: pytest.MonkeyPatch, verdict: bool | None
) -> None:
    _answer_with(monkeypatch, HintText(text="Yes.", reply_moves_forward=verdict))
    assert hint(_replying())["reply_moves_forward"] is verdict


def test_the_prompt_has_the_earlier_conversation(prompts: list[tuple[str, str, str]]) -> None:
    hint(_replying())
    assert prompts[0][2].endswith(
        "Conversation so far:\nStudent: my work\nTutor: What must be true of A?"
    )


def test_the_prompt_has_no_conversation_line_without_a_chat(
    prompts: list[tuple[str, str, str]],
) -> None:
    hint(_state())
    assert "Conversation so far" not in prompts[0][2]


def test_a_failed_model_gives_no_verdict_on_a_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer_with(monkeypatch, None)
    result = hint(_replying())
    assert result["reply_moves_forward"] is None and result["hint_text"] == canned_hint(1)


def test_no_verdict_is_written_for_a_message_that_is_not_a_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answer_with(monkeypatch, HintText(text="Look again.", reply_moves_forward=True))
    assert "reply_moves_forward" not in hint(_state(intent="stuck"))


@pytest.mark.parametrize("answer", [None, HintText(text="   ")])
def test_a_failed_model_on_a_stopped_solution_gives_the_stopped_text(
    answer: HintText | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answer_with(monkeypatch, answer)
    assert hint(_stopped(hint_level=2))["hint_text"] == canned_hint(2, "incomplete")


def test_a_stopped_solution_without_an_error_context_gives_the_stopped_text() -> None:
    state = _state(error_type="incomplete")
    del state["error_context"]
    assert hint(state)["hint_text"] == canned_hint(1, "incomplete")


def _no_working(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "problem": "2x + 1 = 7",
        "intent": "stuck",
        "hint_level": 1,
        "messages": [HumanMessage("idk where to start")],
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


def test_a_student_with_no_working_gets_a_model_hint(prompts: list[tuple[str, str, str]]) -> None:
    result = hint(_no_working())
    assert result["hint_text"] == "What does the 3 multiply in `3(x + 2)`?"
    text = prompts[0][2]
    assert "Starting point:" in text and "Student's message: idk where to start" in text
    assert "wrong step" not in text


def test_a_reply_with_no_working_gets_a_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer_with(monkeypatch, HintText(text="Yes.", reply_moves_forward=True))
    state = _no_working(
        intent="answer",
        hints_used=1,
        messages=[AIMessage("What do you know?"), HumanMessage("it is a product")],
    )
    assert hint(state)["reply_moves_forward"] is True


def test_a_failed_model_gives_the_no_working_canned_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    _answer_with(monkeypatch, None)
    assert hint(_no_working())["hint_text"] == canned_hint(1, NO_WORKING)


def test_a_stale_error_type_does_not_change_the_no_working_prompt(
    prompts: list[tuple[str, str, str]],
) -> None:
    hint(_no_working(error_type="incomplete"))
    assert "Starting point:" in prompts[0][2]
