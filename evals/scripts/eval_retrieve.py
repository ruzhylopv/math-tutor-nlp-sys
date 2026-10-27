"""Eval for `retrieve`: does the right misconception come back in the top 5?

Data: evals/datasets/<split>/retrieve.jsonl. Each query (a problem, the student's steps, the focus
step, the error type and the topic) is run through the real node and the real embedding model
(EMBEDDING_MODEL; the weights are downloaded on first use; no API key). The expected answer is one
catalogue entry. Metrics: Recall@1, @3 and @5, MAP@5 (with one right answer per query it is the mean
reciprocal rank, counting 0 beyond rank 5), the same per source and per category, and the value a
random ranking would get, for context.

Accuracy here is optimistic: the catalogue and the queries are both written by the agent, and the
plain generated queries have the same shape as the catalogue's examples (they are near-copies after
abstraction), so quote the wrapped and hand-written sources. See evals/datasets/README.md.
"""

import logging
from typing import Any

from evals.runner import (
    dataset_path,
    load_jsonl,
    parse_split,
    setup_logging,
    with_progress,
    write_result,
)
from tutor.config import embedding_model_name
from tutor.nodes.retrieve import MIN_SCORE, TOP_K, retrieve
from tutor.state import Step, TutorState
from tutor.tools.catalogue import load_catalogue

COMPONENT = "retrieve"
KS = (1, 3, 5)
logger = logging.getLogger("eval_retrieve")
NOTE = (
    "Optimistic: the catalogue and the queries are written by the agent, and the generated queries "
    "are single-rule rewrites with SymPy-confirmed wrong lines. Report per-source numbers; the "
    "hand-written queries are the discriminating ones."
)


def run_node(case: dict[str, Any]) -> dict[str, Any]:
    """What `retrieve` returns for a case."""
    state: TutorState = {
        "problem": case["problem"],
        "student_steps": [
            Step(claim=step["claim"], justification=step.get("justification", ""))
            for step in case["steps"]
        ],
        "focus_step": case["focus_step"],
        "error_type": case["error_type"],
        "topic": case["topic"],
    }
    return retrieve(state)


def predict(case: dict[str, Any]) -> list[str]:
    """The ids `retrieve` returns for a case, best first."""
    return [match.id for match in run_node(case)["misconception_candidates"]]


def abstention(cases: list[dict[str, Any]], answers: list[str | None]) -> dict[str, float]:
    """How often `retrieve` commits to a misconception (MIN_SCORE), and how often it is right."""
    given = [(case["expected"], answer) for case, answer in zip(cases, answers, strict=True)]
    answered = [(expected, answer) for expected, answer in given if answer is not None]
    return {
        "answered_rate": len(answered) / len(cases),
        "answered_precision": (
            sum(1 for expected, answer in answered if expected == answer) / len(answered)
            if answered
            else 0.0
        ),
        "recall@1_if_forced": sum(1 for expected, answer in given if expected == answer)
        / len(cases),
    }


def _rank(expected: str, ranking: list[str]) -> int | None:
    return ranking.index(expected) + 1 if expected in ranking else None


def _scores(ranks: list[int | None]) -> dict[str, float]:
    n = len(ranks)
    scores = {f"recall@{k}": sum(1 for r in ranks if r is not None and r <= k) / n for k in KS}
    scores["map@5"] = sum(1 / r for r in ranks if r is not None and r <= 5) / n
    return scores


def evaluate(
    cases: list[dict[str, Any]], rankings: list[list[str]], catalogue_size: int
) -> dict[str, float]:
    """All metrics for gold cases and the ids retrieved for each."""
    ranks = [
        _rank(case["expected"], ranking) for case, ranking in zip(cases, rankings, strict=True)
    ]
    metrics = _scores(ranks)
    metrics["random_recall@1"] = 1 / catalogue_size
    metrics["random_recall@5"] = 5 / catalogue_size
    metrics["n"] = float(len(cases))
    for key in ("source", "category"):
        for value in sorted({case[key] for case in cases}):
            subset = [r for case, r in zip(cases, ranks, strict=True) if case[key] == value]
            for name, score in _scores(subset).items():
                metrics[f"{name}/{key}={value}"] = score
            metrics[f"n/{key}={value}"] = float(len(subset))
    return metrics


def main() -> None:
    setup_logging()
    split = parse_split(__doc__)
    path = dataset_path(COMPONENT, split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    cases = load_jsonl(path)
    outputs = [run_node(case) for case in with_progress(cases, "retrieve")]
    rankings = [[match.id for match in out["misconception_candidates"]] for out in outputs]
    metrics = evaluate(cases, rankings, len(load_catalogue()))
    answers = [out["misconception"].id if out["misconception"] else None for out in outputs]
    metrics.update(abstention(cases, answers))
    note = (
        f"{NOTE} Embedding model: {embedding_model_name()}; top {TOP_K} returned; "
        f"MIN_SCORE {MIN_SCORE}. Dev queries are near-copies of catalogue examples, so they "
        "rarely score low: the abstention numbers are optimistic for real off-catalogue steps."
    )
    result = write_result(COMPONENT, split, len(cases), metrics, note=note)
    logger.info("retrieve (%s): n=%d, model %s", split, len(cases), embedding_model_name())
    for source in ("handwritten", "generated_wrapped", "generated"):
        row = "  ".join(
            f"{name}={metrics[f'{name}/source={source}']:.3f}"
            for name in ("recall@1", "recall@3", "recall@5", "map@5")
            if f"{name}/source={source}" in metrics
        )
        logger.info("  %-12s %s", source, row)
    logger.info(
        "  overall      "
        + "  ".join(f"{k}={metrics[k]:.3f}" for k in ("recall@1", "recall@5", "map@5"))
    )
    logger.info(
        "  random       recall@1=%.3f  recall@5=%.3f",
        metrics["random_recall@1"],
        metrics["random_recall@5"],
    )
    logger.info(
        "  abstention   MIN_SCORE=%.2f  answered=%.3f  precision=%.3f",
        MIN_SCORE,
        metrics["answered_rate"],
        metrics["answered_precision"],
    )
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
