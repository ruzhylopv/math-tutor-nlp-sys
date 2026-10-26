"""Eval for `classify`: topic and level against MATH's own labels.

Data: evals/datasets/<split>/classify.jsonl. Each problem is run through the real node, and so
through the real model (needs the key in .env). Answers are cached under evals/.llm_cache, so a
rerun with the same prompt costs nothing and a changed prompt asks again. Successful answers are
cached; a failed call is asked again on a rerun. A failed call counts as a wrong answer and in
`failure_rate`.
"""

import logging
import os
from collections import Counter
from typing import Any

from evals.runner import (
    EVALS_DIR,
    dataset_path,
    load_jsonl,
    parse_split,
    setup_logging,
    write_result,
)
from tutor.config import load_config
from tutor.nodes.classify import classify
from tutor.state import IN_SCOPE_TOPICS

COMPONENT = "classify"
PROMPT = EVALS_DIR.parent / "src" / "tutor" / "prompts" / "classify.md"
logger = logging.getLogger("eval_classify")
NOTE = (
    "Labels are MATH's own subject and level. The eval feeds LaTeX problem text; in use classify "
    "receives parse_input's plain-text problem. Level labels are noisy at the edges, so "
    "within-one is reported too. MATH problems are likely in the model's training data, so the "
    "numbers may be optimistic."
)


def predict(case: dict[str, Any]) -> tuple[str | None, int | None]:
    """The (topic, level) the node returns for a problem, or (None, None) if it failed."""
    result = classify({"problem": case["problem"]})
    return result.get("topic"), result.get("level")


def _f1(true: list[str], pred: list[str], label: str) -> float:
    hits = sum(1 for t, p in zip(true, pred, strict=True) if t == p == label)
    predicted = sum(1 for p in pred if p == label)
    support = sum(1 for t in true if t == label)
    precision = hits / predicted if predicted else 0.0
    recall = hits / support if support else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate(
    cases: list[dict[str, Any]], predictions: list[tuple[str | None, int | None]]
) -> dict[str, float]:
    """All metrics for gold cases and the node's (topic, level) predictions."""
    true_topics = [case["subject"] for case in cases]
    topics = [topic or "(failed)" for topic, _ in predictions]
    n = len(cases)
    labels = sorted(set(true_topics))
    metrics: dict[str, float] = {
        "topic_accuracy": sum(t == p for t, p in zip(true_topics, topics, strict=True)) / n,
        "topic_macro_f1": sum(_f1(true_topics, topics, label) for label in labels) / len(labels),
        "in_scope_accuracy": sum(
            p != "(failed)" and (t in IN_SCOPE_TOPICS) == (p in IN_SCOPE_TOPICS)
            for t, p in zip(true_topics, topics, strict=True)
        )
        / n,
        "level_accuracy": sum(
            case["level"] == level for case, (_, level) in zip(cases, predictions, strict=True)
        )
        / n,
        "level_within_one": sum(
            level is not None and abs(case["level"] - level) <= 1
            for case, (_, level) in zip(cases, predictions, strict=True)
        )
        / n,
        "failure_rate": sum(topic is None for topic, _ in predictions) / n,
    }
    for label in labels:
        support = sum(1 for t in true_topics if t == label)
        metrics[f"support/{label}"] = float(support)
        metrics[f"recall/{label}"] = (
            sum(1 for t, p in zip(true_topics, topics, strict=True) if t == p == label) / support
        )
    for (true, pred), count in sorted(Counter(zip(true_topics, topics, strict=True)).items()):
        if true != pred:
            metrics[f"confusion/{true}->{pred}"] = float(count)
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
    logger.info("classify (%s): n=%d", split, len(cases))
    for name in ("topic_accuracy", "topic_macro_f1", "in_scope_accuracy"):
        logger.info("  %-18s %.3f", name, metrics[name])
    for name in ("level_accuracy", "level_within_one", "failure_rate"):
        logger.info("  %-18s %.3f", name, metrics[name])
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
