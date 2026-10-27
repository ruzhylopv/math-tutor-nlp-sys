"""Shared test setup: no unit test may call the LLM."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from tutor.state import Classification, ParsedInput
from tutor.tools import structured


@pytest.fixture(autouse=True)
def _refuse_real_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nodes call the model through `structured.call_structured`; fail loudly if a test forgets."""

    def refuse(prompt_name: str, schema: type[BaseModel], user_text: str, retries: int = 1) -> None:
        raise AssertionError(f"a unit test called the LLM ({prompt_name}); mock call_structured")

    monkeypatch.setattr(structured, "call_structured", refuse)


@pytest.fixture
def canned_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Replace the model with fixed answers: `canned_llm(Classification=..., ParsedInput=...)`."""

    def install(**answers: BaseModel | None) -> None:
        defaults: dict[str, BaseModel | None] = {
            "Classification": Classification(topic="Algebra", level=2),
            "ParsedInput": ParsedInput(),
        }
        defaults.update(answers)

        def fake(
            prompt_name: str, schema: type[BaseModel], user_text: str, retries: int = 1
        ) -> Any:
            return defaults[schema.__name__]

        monkeypatch.setattr(structured, "call_structured", fake)

    return install
