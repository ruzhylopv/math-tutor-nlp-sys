from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from tutor.nodes.parse_input import parse_input
from tutor.state import ParsedInput, Step, TutorState
from tutor.tools import structured

ATTEMPT = ParsedInput(
    problem="2(y+1) = 10",
    steps=[
        Step(claim="y + 1 = 5", justification="i divide by 2 first"),
        Step(claim="y = 4"),
    ],
)


def _state(text: str, problem: str | None = None) -> TutorState:
    state: TutorState = {"messages": [HumanMessage(text)]}
    if problem is not None:
        state["problem"] = problem
    return state


def test_the_problem_and_the_steps_are_taken_from_the_model_answer(
    canned_llm: Callable[..., None],
) -> None:
    canned_llm(ParsedInput=ATTEMPT)
    result = parse_input(_state("my work: ..."))
    assert result["problem"] == "2(y+1) = 10"
    assert [step.claim for step in result["student_steps"]] == ["y + 1 = 5", "y = 4"]


def test_a_message_without_a_problem_keeps_the_stored_one(canned_llm: Callable[..., None]) -> None:
    canned_llm(ParsedInput=ParsedInput(problem=None, steps=[Step(claim="x = 3")]))
    result = parse_input(_state("x = 3", problem="3x = 9"))
    assert "problem" not in result  # nothing changed, so the stored problem stays
    assert [step.claim for step in result["student_steps"]] == ["x = 3"]


def test_a_new_problem_replaces_the_stored_one(canned_llm: Callable[..., None]) -> None:
    canned_llm(ParsedInput=ParsedInput(problem="x + 1 = 2", steps=[]))
    assert parse_input(_state("new one: x + 1 = 2", problem="3x = 9"))["problem"] == "x + 1 = 2"


def test_a_blank_problem_from_the_model_counts_as_none(canned_llm: Callable[..., None]) -> None:
    canned_llm(ParsedInput=ParsedInput(problem="  ", steps=[]))
    assert "problem" not in parse_input(_state("hmm", problem="3x = 9"))


def test_a_question_resets_the_steps(canned_llm: Callable[..., None]) -> None:
    canned_llm(ParsedInput=ParsedInput(problem=None, steps=[]))
    state = _state("why can't I add the exponents?", problem="x^2 * x^3")
    state["student_steps"] = [Step(claim="old step")]
    assert parse_input(state) == {"student_steps": []}


def test_the_model_sees_the_stored_problem_and_the_latest_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str, str]] = []

    def fake(prompt: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append((prompt, schema.__name__, text))
        return ParsedInput()

    monkeypatch.setattr(structured, "call_structured", fake)
    state: TutorState = {
        "problem": "3x = 9",
        "messages": [HumanMessage("first"), AIMessage("a hint"), HumanMessage("  x = 3  ")],
    }
    parse_input(state)
    assert seen == [
        ("parse_input", "ParsedInput", "Stored problem: 3x = 9\n\nStudent message:\nx = 3")
    ]


def test_with_no_stored_problem_the_model_is_told_none(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(prompt: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append(text)
        return ParsedInput()

    monkeypatch.setattr(structured, "call_structured", fake)
    parse_input(_state("hello"))
    assert seen[0].startswith("Stored problem: none")


def test_a_message_given_as_content_blocks_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake(prompt: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append(text)
        return ParsedInput()

    monkeypatch.setattr(structured, "call_structured", fake)
    blocks: list[str | dict[str, Any]] = [{"type": "text", "text": "x = 3"}, "and more"]
    parse_input({"messages": [HumanMessage(content=blocks)]})
    assert seen[0].endswith("x = 3 and more")


@pytest.mark.parametrize(
    "state", [{}, {"messages": []}, {"messages": [AIMessage("only the tutor")]}]
)
def test_no_student_message_means_no_call_and_no_steps(state: TutorState) -> None:
    assert parse_input(state) == {"student_steps": []}  # a call would fail the test (autouse guard)


def test_a_failing_model_gives_no_steps_and_keeps_the_problem(
    canned_llm: Callable[..., None],
) -> None:
    canned_llm(ParsedInput=None)
    assert parse_input(_state("anything", problem="3x = 9")) == {"student_steps": []}


def test_only_the_declared_fields_are_returned(canned_llm: Callable[..., None]) -> None:
    canned_llm(ParsedInput=ATTEMPT)
    assert set(parse_input(_state("x"))) <= {"problem", "student_steps"}
