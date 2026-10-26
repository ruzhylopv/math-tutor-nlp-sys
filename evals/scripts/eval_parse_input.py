"""Eval for `parse_input`: does it split a messy message into the right problem and steps?

Data: evals/datasets/<split>/parse_input.jsonl. Each message is run through the real node, and so
through the real model (needs the key in .env). Answers are cached under evals/.llm_cache, so a
rerun with the same prompt costs nothing and a changed prompt asks again.

A failed model call counts as wrong in every accuracy (`case_accuracy_answered` leaves those cases
out). `sympy_parse_rate` is the share of predicted claims the checker can read and `gold_parse_rate`
the same over the expected claims: the dataset has correct transcriptions the checker cannot read
(`x = 2 or x = 3`), so read the first against the second.

A case is right when the new problem is the expected one (or both are absent) and the claims match
in number, order and text. Two match rules are reported:
- strict: (problem and steps) equal after removing spaces and a trailing full stop;
- canonical: also ignoring `*`, and brackets around a single number or letter (`x = (19)`).
Both compare text, never algebra, so a "fixed" step cannot pass as a faithful one.
"""

import logging
import os
import re
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from evals.runner import (
    EVALS_DIR,
    dataset_path,
    load_jsonl,
    parse_split,
    setup_logging,
    write_result,
)
from tutor.config import load_config
from tutor.nodes.parse_input import parse_input
from tutor.state import TutorState
from tutor.tools import structured
from tutor.tools.algebra import UnparsableError, parse_statement

COMPONENT = "parse_input"
PROMPT = EVALS_DIR.parent / "src" / "tutor" / "prompts" / "parse_input.md"
logger = logging.getLogger("eval_parse_input")
NOTE = (
    "Messages are rendered from known steps (mined from MATH solutions, some made wrong on "
    "purpose) in a layout and a notation, plus hand-written messages; the expected parse is known "
    "from the rendering, not from a model. Claims are compared as text, so a corrected step fails. "
    "Justifications and operations are not evaluated."
)
Prediction = tuple[str | None, list[str], bool]  # new problem, claims, the model call failed


def norm(text: str) -> str:
    """Strict form: no spaces, no trailing full stop or question mark."""
    return "".join(text.split()).rstrip(".?!,;:")


def canon(text: str) -> str:
    """Canonical form: strict form without `*` and without brackets around one number or letter."""
    text = norm(text).replace("*", "")
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"(?<![\w)])\((\d+(?:\.\d+)?|[A-Za-z])\)", r"\1", text)
    return text


def predict(case: dict[str, Any]) -> Prediction:
    """The node's new problem, its claims, and whether the model call failed, for one case."""
    state: TutorState = {"messages": [HumanMessage(case["message"])]}
    if case.get("stored_problem"):
        state["problem"] = case["stored_problem"]
    failures: list[bool] = []
    real = structured.call_structured

    def spy(*args: Any, **kwargs: Any) -> Any:
        answer = real(*args, **kwargs)
        failures.append(answer is None)
        return answer

    with patch.object(structured, "call_structured", spy):
        result = parse_input(state)
    claims = [step.claim for step in result["student_steps"]]
    return result.get("problem"), claims, any(failures)


def _same(expected: str | None, predicted: str | None, form: Callable[[str], str]) -> bool:
    if expected is None or predicted is None:
        return expected is predicted
    return form(expected) == form(predicted)


def _claims_same(expected: list[str], predicted: list[str], form: Callable[[str], str]) -> bool:
    return len(expected) == len(predicted) and all(
        form(e) == form(p) for e, p in zip(expected, predicted, strict=True)
    )


def _parses(claim: str) -> bool:
    try:
        parse_statement(claim)
    except UnparsableError:
        return False
    return True


def _share(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def evaluate(cases: list[dict[str, Any]], predictions: list[Prediction]) -> dict[str, float]:
    """All metrics for gold cases and the node's predictions."""
    pairs = list(zip(cases, predictions, strict=True))
    failed = [p[2] for _, p in pairs]  # a failed call is wrong, even when nothing was expected
    problem_ok = [
        not f and _same(c["expected_problem"], p[0], canon)
        for (c, p), f in zip(pairs, failed, strict=True)
    ]
    problem_strict_ok = [
        not f and _same(c["expected_problem"], p[0], norm)
        for (c, p), f in zip(pairs, failed, strict=True)
    ]
    strict_ok = [
        not f and _claims_same(c["expected_steps"], p[1], norm)
        for (c, p), f in zip(pairs, failed, strict=True)
    ]
    canon_ok = [
        not f and _claims_same(c["expected_steps"], p[1], canon)
        for (c, p), f in zip(pairs, failed, strict=True)
    ]
    case_ok = [a and b for a, b in zip(problem_ok, canon_ok, strict=True)]
    case_strict_ok = [a and b for a, b in zip(problem_strict_ok, strict_ok, strict=True)]
    expected_total = sum(len(c["expected_steps"]) for c in cases)
    position_hits = {
        name: sum(
            form(e) == form(p[1][i])
            for c, p in pairs
            for i, e in enumerate(c["expected_steps"])
            if i < len(p[1])
        )
        for name, form in (("exact", norm), ("canonical", canon))
    }
    claims = [claim for _, p in pairs for claim in p[1]]
    metrics: dict[str, float] = {
        "case_accuracy": _share(case_ok),
        "case_accuracy_answered": _share(
            [ok for ok, f in zip(case_ok, failed, strict=True) if not f]
        ),
        "case_accuracy_strict": _share(case_strict_ok),
        "problem_accuracy": _share(problem_ok),
        "steps_accuracy": _share(canon_ok),
        "steps_accuracy_strict": _share(strict_ok),
        "claim_recall_exact": position_hits["exact"] / expected_total if expected_total else 0.0,
        "claim_recall_canonical": position_hits["canonical"] / expected_total
        if expected_total
        else 0.0,
        "step_count_accuracy": _share(
            [not p[2] and len(c["expected_steps"]) == len(p[1]) for c, p in pairs]
        ),
        "invented_steps_rate": _share([len(p[1]) > len(c["expected_steps"]) for c, p in pairs]),
        "dropped_steps_rate": _share([len(p[1]) < len(c["expected_steps"]) for c, p in pairs]),
        "sympy_parse_rate": _share([_parses(claim) for claim in claims]),
        "gold_parse_rate": _share([_parses(claim) for c in cases for claim in c["expected_steps"]]),
        "failure_rate": _share(failed),
    }
    no_working = [not p[2] and p[1] == [] for c, p in pairs if not c["expected_steps"]]
    metrics["no_working_accuracy"] = _share(no_working)
    metrics["n/no_working"] = float(len(no_working))
    for feature in sorted({f for c in cases for f in c["features"]}):
        flags = [ok for (c, _), ok in zip(pairs, case_ok, strict=True) if feature in c["features"]]
        metrics[f"case_accuracy/feature={feature}"] = _share(flags)
        metrics[f"n/feature={feature}"] = float(len(flags))
    for source in sorted({c["source"] for c in cases}):
        flags = [ok for (c, _), ok in zip(pairs, case_ok, strict=True) if c["source"] == source]
        metrics[f"case_accuracy/source={source}"] = _share(flags)
        metrics[f"n/source={source}"] = float(len(flags))
    return metrics


def main() -> None:
    setup_logging()
    split = parse_split(__doc__)
    path = dataset_path(COMPONENT, split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    os.environ.setdefault("LLM_CACHE_DIR", str(EVALS_DIR / ".llm_cache"))
    config = load_config()
    cases = load_jsonl(path)
    metrics = evaluate(cases, [predict(case) for case in cases])
    result = write_result(
        COMPONENT,
        split,
        len(cases),
        metrics,
        model_name=config.model_name,
        prompt_path=PROMPT,
        note=NOTE,
    )
    logger.info("parse_input (%s): n=%d", split, len(cases))
    for name in (
        "case_accuracy",
        "case_accuracy_answered",
        "case_accuracy_strict",
        "problem_accuracy",
        "steps_accuracy",
        "claim_recall_canonical",
        "no_working_accuracy",
        "invented_steps_rate",
        "dropped_steps_rate",
        "sympy_parse_rate",
        "gold_parse_rate",
        "failure_rate",
    ):
        logger.info("  %-24s %.3f", name, metrics[name])
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
