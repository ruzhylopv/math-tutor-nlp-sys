from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from tutor.nodes.classify import classify
from tutor.state import Classification, TutorState
from tutor.tools import structured


def test_the_model_answer_becomes_topic_and_level(canned_llm: Callable[..., None]) -> None:
    canned_llm(Classification=Classification(topic="Intermediate Algebra", level=4))
    assert classify({"problem": "Find the roots of $x^3 - 2x^2 - 5x + 6$."}) == {
        "topic": "Intermediate Algebra",
        "level": 4,
    }


def test_the_problem_text_is_what_the_model_sees(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str, str]] = []

    def fake(prompt: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        seen.append((prompt, schema.__name__, text))
        return Classification(topic="Algebra", level=1)

    monkeypatch.setattr(structured, "call_structured", fake)
    classify({"problem": "  Solve 3x = 9.  "})
    assert seen == [("classify", "Classification", "Solve 3x = 9.")]


@pytest.mark.parametrize("state", [{}, {"problem": ""}, {"problem": "   "}])
def test_no_problem_means_no_call_and_no_change(state: TutorState) -> None:
    assert classify(state) == {}  # the autouse fixture would fail the test on any LLM call


def test_a_failing_model_changes_nothing(canned_llm: Callable[..., None]) -> None:
    canned_llm(Classification=None)
    assert classify({"problem": "Solve 3x = 9."}) == {}


def test_only_the_declared_fields_are_returned(canned_llm: Callable[..., None]) -> None:
    canned_llm()
    assert set(classify({"problem": "x"})) == {"topic", "level"}


def test_the_model_cannot_return_an_unknown_subject_or_level() -> None:
    with pytest.raises(ValueError):
        Classification(topic="Cooking", level=2)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Classification(topic="Algebra", level=6)
