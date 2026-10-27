"""The one place where an LLM node talks to the model.

`call_structured` sends a prompt (loaded from src/tutor/prompts/) and the user's text, asks for a
pydantic schema, retries once, and returns None if the output is still invalid. Nodes call only this
function, and unit tests mock it, so no node touches the network.

Only transient or invalid-output failures are retried (see `_RETRYABLE`): connection errors and
timeouts, 429, 5xx, a truncated or filtered answer, and output that does not parse (a ValueError,
which covers pydantic's ValidationError and langchain's OutputParserException) and a model refusal
(OpenAIRefusalError). A provider that answers HTTP 200 with a bad body (an `{"error": ...}` object,
an HTML page, an empty `choices` list) makes the SDK raise TypeError, AttributeError or IndexError;
these are provider failures, so they are retried too. The price is that a programming bug of those
three types in the call would also be retried once and then give None with the class name logged;
that is accepted, because the node tests mock this function. Setup errors are raised, not
swallowed: a missing key (ConfigError), a wrong or revoked key (401, 403) and a bad request (400),
so a broken eval fails at once instead of giving N silent Nones.

For evals, set LLM_CACHE_DIR: each answer is stored under a hash of the model, the prompt, the
schema and the user text, so a rerun costs nothing and a changed prompt invalidates itself.
"""

import hashlib
import json
import logging
from pathlib import Path

import openai
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai.chat_models.base import OpenAIRefusalError
from pydantic import BaseModel

from tutor.config import load_config
from tutor.llm import get_llm
from tutor.prompts import load_prompt

logger = logging.getLogger("tutor.structured")

# The openai SDK already retries connection errors, 429 and 5xx twice with backoff
# (default max_retries=2), so our single retry is mainly for invalid output.
_RETRYABLE = (
    openai.APIConnectionError,  # includes APITimeoutError
    openai.RateLimitError,
    openai.InternalServerError,
    openai.LengthFinishReasonError,
    openai.ContentFilterFinishReasonError,
    # Besides pydantic's ValidationError and langchain's OutputParserException (both subclasses),
    # a bare ValueError is needed: empty or invalid provider content arrives as a plain ValueError.
    ValueError,
    OpenAIRefusalError,  # a refusal is invalid output (plain Exception subclass)
    TypeError,  # HTTP 200 with a malformed body, raised inside the SDK parsing
    AttributeError,  # same: e.g. an HTML body parsed as a string
    IndexError,  # same: an empty `choices` list
    TimeoutError,  # builtin; the SDK wraps transport errors as APIConnectionError
    ConnectionError,
)


def _cache_path(
    cache_dir: str, model: str, prompt: str, schema: type[BaseModel], text: str
) -> Path:
    key = json.dumps([model, prompt, schema.model_json_schema(), text], sort_keys=True)
    return Path(cache_dir) / f"{hashlib.sha256(key.encode()).hexdigest()}.json"


def call_structured[T: BaseModel](
    prompt_name: str, schema: type[T], user_text: str, retries: int = 1
) -> T | None:
    """Ask the model for a `schema` answer about `user_text`; None if it stays invalid."""
    config = load_config()
    prompt = load_prompt(prompt_name)
    cache = (
        _cache_path(config.llm_cache_dir, config.model_name, prompt, schema, user_text)
        if config.llm_cache_dir
        else None
    )
    if cache is not None and cache.exists():
        try:
            return schema.model_validate_json(cache.read_text(encoding="utf-8"))
        except ValueError:
            logger.warning("ignoring a corrupt cache entry %s", cache.name)
    chain = get_llm(config).with_structured_output(schema, method="json_schema")
    messages = [SystemMessage(prompt), HumanMessage(user_text)]
    for attempt in range(1, retries + 2):
        try:
            result = chain.invoke(messages)
        except _RETRYABLE as exc:  # anything else (401, 403, 400, a bug) propagates
            logger.warning(
                "%s attempt %d failed: %s (status %s)",
                prompt_name,
                attempt,
                type(exc).__name__,
                getattr(exc, "status_code", None),
            )
            continue
        if isinstance(result, schema):
            if cache is not None:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(result.model_dump_json(), encoding="utf-8")
            return result
        logger.warning("%s attempt %d returned no %s", prompt_name, attempt, schema.__name__)
    return None
