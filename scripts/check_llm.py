"""One real call per structured-output method, to see what the chosen OpenRouter model supports.

Run by hand: `uv run python scripts/check_llm.py`. Makes network calls with the key in .env;
it is not part of the test suite.
"""

import logging
from typing import Literal, get_args

from tutor.config import load_config
from tutor.llm import get_llm
from tutor.state import Decision

logger = logging.getLogger("check_llm")

METHODS = get_args(Literal["json_schema", "function_calling", "json_mode"])
PROMPT = (
    "A student wrote only 'x = 13/3' for a homework problem and showed no working. "
    "Choose the next action (ask, diagnose, hint or reply) and give a short reason."
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config()
    logger.info("model: %s", config.model_name)
    llm = get_llm(config)
    for method in METHODS:
        try:
            chain = llm.with_structured_output(Decision, method=method)
            result = chain.invoke(PROMPT)
            logger.info("%-17s OK   %r", method, result)
        except Exception as exc:  # report any provider or parsing failure per method
            logger.info("%-17s FAIL %s: %s", method, type(exc).__name__, str(exc)[:200])


if __name__ == "__main__":
    main()
