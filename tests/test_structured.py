from pathlib import Path
from typing import Any

import pytest

from tutor.config import ConfigError
from tutor.prompts import load_prompt
from tutor.state import Classification
from tutor.tools import structured
from tutor.tools.structured import call_structured

GOOD = Classification(topic="Algebra", level=2)


class FakeChain:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.calls: list[Any] = []

    def invoke(self, messages: Any) -> Any:
        self.calls.append(messages)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


class FakeLLM:
    def __init__(self, chain: FakeChain) -> None:
        self.chain = chain
        self.method: str | None = None

    def with_structured_output(self, schema: Any, method: str) -> FakeChain:
        self.method = method
        return self.chain


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")
    monkeypatch.setenv("MODEL_NAME", "some/model")
    monkeypatch.delenv("LLM_CACHE_DIR", raising=False)


def _use(monkeypatch: pytest.MonkeyPatch, *outputs: Any) -> tuple[FakeLLM, FakeChain]:
    chain = FakeChain(list(outputs))
    llm = FakeLLM(chain)
    monkeypatch.setattr(structured, "get_llm", lambda config: llm)
    return llm, chain


def test_a_valid_answer_is_returned_with_the_prompt_and_the_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm, chain = _use(monkeypatch, GOOD)
    assert call_structured("classify", Classification, "Simplify $x+x$.") == GOOD
    assert llm.method == "json_schema"
    system, human = chain.calls[0]
    assert system.content == load_prompt("classify") and human.content == "Simplify $x+x$."


def test_a_failed_call_is_retried_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _, chain = _use(monkeypatch, TimeoutError("slow"), GOOD)
    assert call_structured("classify", Classification, "x") == GOOD
    assert len(chain.calls) == 2


def test_an_answer_of_the_wrong_type_counts_as_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    _, chain = _use(monkeypatch, None, "plain text")
    assert call_structured("classify", Classification, "x") is None
    assert len(chain.calls) == 2


def test_two_failures_give_none_instead_of_an_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, ValueError("bad json"), ConnectionError("down"))
    assert call_structured("classify", Classification, "x") is None


def test_no_retries_means_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    _, chain = _use(monkeypatch, None, GOOD)
    assert call_structured("classify", Classification, "x", retries=0) is None
    assert len(chain.calls) == 1


def test_a_missing_key_is_a_setup_error_and_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(ConfigError):
        call_structured("classify", Classification, "x")


# --- the eval cache ---------------------------------------------------------------------------
def test_a_cached_answer_costs_no_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    _, chain = _use(monkeypatch, GOOD)
    assert call_structured("classify", Classification, "same text") == GOOD
    assert call_structured("classify", Classification, "same text") == GOOD
    assert len(chain.calls) == 1


def test_another_text_or_another_prompt_is_a_new_question(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    _, chain = _use(monkeypatch, GOOD, GOOD, GOOD)
    call_structured("classify", Classification, "one")
    call_structured("classify", Classification, "two")
    monkeypatch.setattr(structured, "load_prompt", lambda name: "a changed prompt")
    call_structured("classify", Classification, "one")
    assert len(chain.calls) == 3


def test_a_corrupt_cache_entry_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    _, chain = _use(monkeypatch, GOOD, GOOD)
    call_structured("classify", Classification, "x")
    (entry,) = tmp_path.glob("*.json")
    entry.write_text("not json", encoding="utf-8")
    assert call_structured("classify", Classification, "x") == GOOD
    assert len(chain.calls) == 2


def test_an_invalid_answer_is_not_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    _use(monkeypatch, None, None)
    assert call_structured("classify", Classification, "x") is None
    assert list(tmp_path.glob("*.json")) == []


def test_nothing_is_written_without_a_cache_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _use(monkeypatch, GOOD)
    call_structured("classify", Classification, "x")
    assert list(tmp_path.iterdir()) == []


# --- the prompt loader ------------------------------------------------------------------------
def test_a_prompt_is_loaded_by_name() -> None:
    assert "## Role" in load_prompt("classify")


@pytest.mark.parametrize("name", ["../config", "a/b", "classify.md", "", "x y", "classify\n"])
def test_only_plain_prompt_names_are_accepted(name: str) -> None:
    with pytest.raises(ValueError):
        load_prompt(name)
