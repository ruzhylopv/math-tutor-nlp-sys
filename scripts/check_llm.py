"""Try each structured-output method a few times against the chosen OpenRouter model.

Run by hand: `uv run python scripts/check_llm.py`. Makes network calls with the key in .env; it is
not part of the test suite. Exits non-zero if no method works every time. The prompt below is a
manual probe, not a graph node, so the "prompts live in src/tutor/prompts/" rule does not apply.
"""

import logging
import sys
from typing import Literal

from langchain_openai import ChatOpenAI

from tutor.config import load_config
from tutor.llm import get_llm
from tutor.state import Decision

logger = logging.getLogger("check_llm")

Method = Literal["json_schema", "function_calling", "json_mode"]
METHODS: tuple[Method, ...] = ("json_schema", "function_calling", "json_mode")
ATTEMPTS = 3
PROMPT = (
    "A student wrote only 'x = 13/3' for a homework problem and showed no working. "
    "Choose the next action (ask, diagnose, hint or reply) and give a short reason. "
    'Answer as JSON with the keys "action" and "reason".'
)


def count_successes(llm: ChatOpenAI, method: Method) -> int:
    """Number of attempts (out of ATTEMPTS) that returned a valid Decision."""
    chain = llm.with_structured_output(Decision, method=method)
    successes = 0
    for attempt in range(1, ATTEMPTS + 1):
        try:
            result = chain.invoke(PROMPT)
            if isinstance(result, Decision):
                successes += 1
                logger.info("  %s attempt %d OK   %s", method, attempt, result)
            else:  # e.g. function_calling returns None when the model answers in plain text
                logger.info(
                    "  %s attempt %d FAIL no structured output: %r", method, attempt, result
                )
        except Exception as exc:  # report any provider or parsing failure per attempt
            logger.info(
                "  %s attempt %d FAIL %s: %s", method, attempt, type(exc).__name__, str(exc)[:200]
            )
    return successes


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config()
    logger.info("model: %s", config.model_name)
    llm = get_llm(config)
    scores = {method: count_successes(llm, method) for method in METHODS}
    for method, ok in scores.items():
        logger.info("%-17s %d/%d", method, ok, ATTEMPTS)
    usable = [method for method, ok in scores.items() if ok == ATTEMPTS]
    flaky = [method for method, ok in scores.items() if 0 < ok < ATTEMPTS]
    logger.info("usable methods: %s", ", ".join(usable) or "none")
    if flaky:
        logger.info("flaky (worked sometimes): %s", ", ".join(flaky))
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
