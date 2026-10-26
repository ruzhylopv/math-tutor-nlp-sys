import logging
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest
from langchain_core.exceptions import OutputParserException
from langchain_openai.chat_models.base import OpenAIRefusalError
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, ValidationError

from tutor.config import ConfigError
from tutor.prompts import load_prompt
from tutor.state import Classification
from tutor.tools import structured
from tutor.tools.structured import call_structured

GOOD = Classification(topic="Algebra", level=2)
_REQUEST = httpx.Request("POST", "https://example.invalid/v1/chat/completions")


_COMPLETION = ChatCompletion(id="c", object="chat.completion", created=0, model="m", choices=[])


class Other(BaseModel):
    answer: str


def _status_error(cls: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    return cls("boom", response=httpx.Response(status, request=_REQUEST), body=None)


def _validation_error() -> ValidationError:
    try:
        Classification.model_validate_json("x")
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


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
        self.schema: Any = None

    def with_structured_output(self, schema: Any, method: str) -> FakeChain:
        self.method = method
        self.schema = schema
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
    assert llm.method == "json_schema" and llm.schema is Classification
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


@pytest.mark.parametrize(
    "error",
    [
        openai.APIConnectionError(request=_REQUEST),
        openai.APITimeoutError(request=_REQUEST),
        _status_error(openai.RateLimitError, 429),
        _status_error(openai.InternalServerError, 500),
        openai.LengthFinishReasonError(completion=_COMPLETION),
        openai.ContentFilterFinishReasonError(),
        _validation_error(),
        OutputParserException("bad output"),
        OpenAIRefusalError("I cannot help with that"),
        # HTTP 200 with a malformed body: the SDK fails while parsing it
        TypeError("'NoneType' object is not iterable"),
        AttributeError("'str' object has no attribute 'choices'"),
        IndexError("list index out of range"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_transient_provider_errors_are_retried_once_then_give_none(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    _, chain = _use(monkeypatch, error, error)
    assert call_structured("classify", Classification, "x") is None
    assert len(chain.calls) == 2


@pytest.mark.parametrize(
    "error",
    [
        _status_error(openai.AuthenticationError, 401),
        _status_error(openai.PermissionDeniedError, 403),
        _status_error(openai.BadRequestError, 400),
        RuntimeError("a bug"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_setup_errors_and_bugs_propagate_without_a_retry(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    _, chain = _use(monkeypatch, error, GOOD)
    with pytest.raises(type(error)):
        call_structured("classify", Classification, "x")
    assert len(chain.calls) == 1


def test_a_rate_limit_logs_its_status_code(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    error = _status_error(openai.RateLimitError, 429)
    _use(monkeypatch, error, error)
    with caplog.at_level(logging.WARNING):
        assert call_structured("classify", Classification, "x") is None
    assert "RateLimitError" in caplog.text and "status 429" in caplog.text


def test_logs_hold_neither_the_student_text_nor_secrets(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    text = "my private solution 7q9z"
    _use(monkeypatch, ValueError("secret-key " + text), ValueError("secret-key " + text))
    with caplog.at_level(logging.DEBUG):
        assert call_structured("classify", Classification, text) is None
    assert "attempt" in caplog.text  # something was logged
    assert text not in caplog.text
    assert "secret-key" not in caplog.text


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


def test_another_model_is_a_new_question(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    _, chain = _use(monkeypatch, GOOD, GOOD)
    call_structured("classify", Classification, "x")
    monkeypatch.setenv("MODEL_NAME", "another/model")
    call_structured("classify", Classification, "x")
    assert len(chain.calls) == 2


def test_another_schema_is_a_new_question(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    other = Other(answer="a")
    _, chain = _use(monkeypatch, GOOD, other)
    assert call_structured("classify", Classification, "x") == GOOD
    assert call_structured("classify", Other, "x") == other
    assert len(chain.calls) == 2


@pytest.mark.parametrize("content", ["not json", '{"topic": "Algebra"}'])
def test_a_corrupt_cache_entry_is_ignored_and_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str
) -> None:
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path))
    _, chain = _use(monkeypatch, GOOD, GOOD)
    call_structured("classify", Classification, "x")
    (entry,) = tmp_path.glob("*.json")
    entry.write_text(content, encoding="utf-8")
    assert call_structured("classify", Classification, "x") == GOOD
    assert len(chain.calls) == 2
    assert call_structured("classify", Classification, "x") == GOOD  # now a cache hit
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
    path = Path(__file__).parents[1] / "src" / "tutor" / "prompts" / "classify.md"
    assert load_prompt("classify") == path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["../config", "a/b", "classify.md", "", "x y", "classify\n"])
def test_only_plain_prompt_names_are_accepted(name: str) -> None:
    with pytest.raises(ValueError):
        load_prompt(name)
