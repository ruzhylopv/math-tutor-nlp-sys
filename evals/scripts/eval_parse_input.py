"""Eval for `parse_input`: does it split a messy message into the right problem and steps?

Data: evals/datasets/<split>/parse_input.jsonl. Each message is run through the real node, and so
through the real model (needs the key in .env). Answers are cached under evals/.llm_cache, so a
rerun with the same prompt costs nothing and a changed prompt asks again.

A failed model call counts as wrong in every accuracy (`case_accuracy_answered` leaves those cases
out). `sympy_parse_rate` is the share of predicted claims the checker can read and `gold_parse_rate`
the same over the expected claims: the dataset has correct transcriptions the checker cannot read
(`x = 2 or x = 3`), so read the first against the second.

Use `--limit N` for a quick run on N messages taken in turn from each kind (the result file
says so). The cases labelled with line kinds and intent (`expected_intent`) are always run in full.

Line kinds and intent: `kind_accuracy` is per expected step, by position (a missing step is wrong),
and `intent_accuracy` per message, both over the labelled cases only.

Topic and level (merged from `classify`): the MATH problems of
evals/datasets/<split>/classify.jsonl are sent as the student's message, and the node's topic and
level are scored against MATH's labels (`topic/...`). `--limit N` takes N problems in turn from
each subject.

A case is right when the new problem is the expected one (or both are absent) and the claims match
in number, order and text. Two match rules are reported:
- strict: (problem and steps) equal after removing spaces and a trailing full stop;
- canonical: also ignoring `*`, and brackets around a single number or letter (`x = (19)`).
Both compare text, never algebra, so a "fixed" step cannot pass as a faithful one.
"""

import hashlib
import logging
import os
import re
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage

from evals.runner import (
    EVALS_DIR,
    dataset_path,
    load_jsonl,
    parse_split_and_limit,
    setup_logging,
    with_progress,
    write_result,
)
from tutor.config import load_config
from tutor.nodes.parse_input import parse_input
from tutor.state import IN_SCOPE_TOPICS, TutorState
from tutor.tools import structured
from tutor.tools.algebra import UnparsableError, parse_statement

COMPONENT = "parse_input"
PROMPT = EVALS_DIR.parent / "src" / "tutor" / "prompts" / "parse_input.md"
logger = logging.getLogger("eval_parse_input")
NOTE = (
    "Messages are rendered from known steps (mined from MATH solutions, some made wrong on "
    "purpose) in a layout and a notation, plus hand-written messages; the expected parse is known "
    "from the rendering, not from a model. Claims are compared as text, so a corrected step fails. "
    "Justifications and operations are not evaluated. Line kinds and intent are scored on "
    "hand-written dev cases only; topic and level on MATH problems sent as the message (LaTeX "
    "text, likely in the model's training data)."
)
Prediction = tuple[str | None, list[str], bool]  # new problem, claims, the model call failed
Reading = tuple[Prediction, list[str], str | None]  # also the kinds and the intent (None: failed)
TopicPrediction = tuple[str | None, int | None, bool]  # topic, level, the model call failed


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


def _run(state: TutorState) -> tuple[dict[str, Any], bool]:
    """The node's update for a state, and whether the model call failed."""
    failures: list[bool] = []
    real = structured.call_structured

    def spy(*args: Any, **kwargs: Any) -> Any:
        answer = real(*args, **kwargs)
        failures.append(answer is None)
        return answer

    with patch.object(structured, "call_structured", spy):
        result = parse_input(state)
    return result, any(failures)


def predict(case: dict[str, Any]) -> Reading:
    """The node's new problem, claims, failure flag, line kinds and intent for one case."""
    state: TutorState = {"messages": [HumanMessage(case["message"])]}
    if case.get("tutor_message"):
        state["messages"] = [AIMessage(case["tutor_message"]), HumanMessage(case["message"])]
    if case.get("stored_problem"):
        state["problem"] = case["stored_problem"]
    result, failed = _run(state)
    steps = result["student_steps"]
    prediction = (result.get("problem"), [step.claim for step in steps], failed)
    return prediction, [step.kind for step in steps], result.get("intent")


def predict_topic(case: dict[str, Any]) -> TopicPrediction:
    """The topic and level the node gives a MATH problem sent as the message."""
    result, failed = _run({"messages": [HumanMessage(case["problem"])]})
    return result.get("topic"), result.get("level"), failed


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


def evaluate_labels(cases: list[dict[str, Any]], readings: list[Reading]) -> dict[str, float]:
    """Line-kind and intent accuracy over the cases labelled with an intent."""
    pairs = [(c, r) for c, r in zip(cases, readings, strict=True) if "expected_intent" in c]
    kind_hits = [
        not r[0][2] and i < len(r[1]) and r[1][i] == kind
        for c, r in pairs
        for i, kind in enumerate(c["expected_kinds"])
    ]
    metrics = {
        "kind_accuracy": _share(kind_hits),
        "intent_accuracy": _share([not r[0][2] and r[2] == c["expected_intent"] for c, r in pairs]),
        "n/labelled": float(len(pairs)),
        "n/labelled_steps": float(len(kind_hits)),
    }
    for intent in sorted({c["expected_intent"] for c, _ in pairs}):
        flags = [r[2] == intent for c, r in pairs if c["expected_intent"] == intent]
        metrics[f"intent_recall/{intent}"] = _share(flags)
    return metrics


def _f1(true: list[str], pred: list[str], label: str) -> float:
    hits = sum(1 for t, p in zip(true, pred, strict=True) if t == p == label)
    predicted = sum(1 for p in pred if p == label)
    support = sum(1 for t in true if t == label)
    precision = hits / predicted if predicted else 0.0
    recall = hits / support if support else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate_topics(
    cases: list[dict[str, Any]], predictions: list[TopicPrediction]
) -> dict[str, float]:
    """Topic and level against MATH's labels; a missing topic or a failed call is wrong."""
    true = [case["subject"] for case in cases]
    topics = [topic or "(none)" for topic, _, _ in predictions]
    labels = sorted(set(true))
    pairs = list(zip(cases, predictions, strict=True))
    return {
        "topic/accuracy": _share([t == p for t, p in zip(true, topics, strict=True)]),
        "topic/macro_f1": sum(_f1(true, topics, label) for label in labels) / len(labels)
        if labels
        else 0.0,
        "topic/in_scope_accuracy": _share(
            [
                p != "(none)" and (t in IN_SCOPE_TOPICS) == (p in IN_SCOPE_TOPICS)
                for t, p in zip(true, topics, strict=True)
            ]
        ),
        "topic/level_accuracy": _share([c["level"] == p[1] for c, p in pairs]),
        "topic/level_within_one": _share(
            [p[1] is not None and abs(c["level"] - p[1]) <= 1 for c, p in pairs]
        ),
        "topic/failure_rate": _share([p[2] for p in predictions]),
        "topic/n": float(len(cases)),
    }


def topic_sample(cases: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """`limit` MATH problems taken in turn from each subject (deterministic, like the other)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for case in sorted(cases, key=lambda case: hashlib.sha256(case["id"].encode()).hexdigest()):
        groups.setdefault(case["subject"], []).append(case)
    queues = [groups[subject] for subject in sorted(groups)]
    chosen: list[dict[str, Any]] = []
    while len(chosen) < limit and any(queues):
        for queue in queues:
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
    return sorted(chosen, key=lambda case: str(case["id"]))


def stratified_sample(cases: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """`limit` cases, taken in turn from each kind of message (hand-written ones are a kind).

    Deterministic: inside a kind cases are ordered by a hash of their id, so the same subset is
    chosen on every run and the cache stays valid. A limit above the size returns everything.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    ordered = sorted(cases, key=lambda case: hashlib.sha256(case["id"].encode()).hexdigest())
    for case in ordered:
        kind = "handwritten" if case["source"] == "handwritten" else case["features"][0]
        groups.setdefault(kind, []).append(case)
    queues = [groups[kind] for kind in sorted(groups)]
    chosen: list[dict[str, Any]] = []
    while len(chosen) < limit and any(queues):
        for queue in queues:
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
    return sorted(chosen, key=lambda case: str(case["id"]))


def main() -> None:
    setup_logging()
    split, limit = parse_split_and_limit(__doc__)
    path = dataset_path(COMPONENT, split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    os.environ.setdefault("LLM_CACHE_DIR", str(EVALS_DIR / ".llm_cache"))
    config = load_config()
    cases = load_jsonl(path)
    note = NOTE
    labelled = [case for case in cases if "expected_intent" in case]
    rest = [case for case in cases if "expected_intent" not in case]
    if limit is not None and limit < len(rest):
        note += (
            f" SUBSET: {limit} of {len(rest)} messages, taken in turn from each kind, plus all "
            f"{len(labelled)} labelled with kinds and intent."
        )
        cases = sorted(stratified_sample(rest, limit) + labelled, key=lambda c: str(c["id"]))
    readings = [predict(case) for case in with_progress(cases, "parse_input")]
    metrics = evaluate(cases, [reading[0] for reading in readings])
    metrics.update(evaluate_labels(cases, readings))
    topic_path = dataset_path("classify", split)
    if topic_path.exists():
        problems = load_jsonl(topic_path)
        if limit is not None and limit < len(problems):
            note += f" TOPIC SUBSET: {limit} of {len(problems)} problems, in turn by subject."
            problems = topic_sample(problems, limit)
        topics = [predict_topic(case) for case in with_progress(problems, "parse_input topics")]
        metrics.update(evaluate_topics(problems, topics))
    result = write_result(
        COMPONENT,
        split,
        len(cases),
        metrics,
        model_name=config.model_name,
        prompt_path=PROMPT,
        note=note,
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
        "kind_accuracy",
        "intent_accuracy",
        "topic/accuracy",
        "topic/macro_f1",
        "topic/level_within_one",
        "topic/failure_rate",
    ):
        if name in metrics:
            logger.info("  %-24s %.3f", name, metrics[name])
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
