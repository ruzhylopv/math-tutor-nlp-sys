from typing import Any

import pytest
from pydantic import BaseModel

from tutor.nodes.hint import hint
from tutor.state import ErrorContext, HintText, Misconception, TutorState
from tutor.tools import structured
from tutor.tools.canned_hints import MAX_LEVEL, canned_hint
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
