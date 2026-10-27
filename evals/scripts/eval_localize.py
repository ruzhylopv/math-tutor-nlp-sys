"""Eval for `localize` on evals/datasets/<split>/localize.jsonl: where the error is and what type.

Each case (a problem and the student's steps) is run through the real `verify` and then
`localize`, because `localize` reads `verify`'s verdicts. Both are deterministic, so there is no
model, no cache and the result file records a null model name. Metrics are flat floats: accuracy of
each field and of all three together, precision, recall and support per error type (`none` is the
clean outcome), the mismatch detection rate (recall of `reasoning_result_mismatch`), accuracy per
kind and per source, and confusion counts.

Accuracy here is high by construction for the generated cases (the corrupted step is known and the
chain was selected with `verify`); the hand-written cases are the discriminating ones. See
evals/datasets/README.md.
"""

import logging
from collections import Counter
from typing import Any

from evals.runner import dataset_path, load_jsonl, parse_split, setup_logging, write_result
from tutor.nodes.localize import localize
from tutor.nodes.verify import verify
from tutor.state import Step, TutorState

COMPONENT = "localize"
TYPES = (
    "algebraic_transformation",
    "omission_extraneous_root",
    "reasoning_result_mismatch",
    "other",
    "none",
)
NOTE = (
    "Deterministic: verify then localize, no model. Generated cases are high by construction "
    "(the corrupted step is known and the chain was selected with verify); the hand-written cases "
    "are the discriminating ones. See evals/datasets/README.md."
)
logger = logging.getLogger("eval_localize")
Outcome = tuple[int | None, int | None, str]


def predict(case: dict[str, Any]) -> Outcome:
    """(first_error_step, focus_step, error type or "none") from verify then localize."""
    state: TutorState = {
        "problem": case["problem"],
        "student_steps": [
            Step(
                claim=step["claim"],
                justification=step.get("justification", ""),
                justification_claim=step.get("justification_claim"),
            )
            for step in case["steps"]
        ],
    }
    state.update(verify(state))  # type: ignore[typeddict-item]
    result = localize(state)
    return result["first_error_step"], result["focus_step"], result["error_type"] or "none"


def _expected(case: dict[str, Any]) -> Outcome:
    expected = case["expected"]
    return expected["first_error_step"], expected["focus_step"], expected["error_type"] or "none"


def _share(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def evaluate(cases: list[dict[str, Any]], predictions: list[Outcome]) -> dict[str, float]:
    """All metrics for gold cases and the pipeline's outcomes."""
    gold = [_expected(case) for case in cases]
    first = [g[0] == p[0] for g, p in zip(gold, predictions, strict=True)]
    focus = [g[1] == p[1] for g, p in zip(gold, predictions, strict=True)]
    kind = [g[2] == p[2] for g, p in zip(gold, predictions, strict=True)]
    exact = [a and b and c for a, b, c in zip(first, focus, kind, strict=True)]
    metrics: dict[str, float] = {
        "case_accuracy": _share(exact),
        "first_error_step_accuracy": _share(first),
        "focus_step_accuracy": _share(focus),
        "error_type_accuracy": _share(kind),
    }
    for name in TYPES:
        support = sum(1 for g in gold if g[2] == name)
        predicted = sum(1 for p in predictions if p[2] == name)
        hits = sum(1 for g, p in zip(gold, predictions, strict=True) if g[2] == p[2] == name)
        metrics[f"support/{name}"] = float(support)
        metrics[f"recall/{name}"] = hits / support if support else 0.0
        if predicted:  # precision is undefined, not 0, for a type that was never predicted
            metrics[f"precision/{name}"] = hits / predicted
    metrics["mismatch_detection_rate"] = metrics["recall/reasoning_result_mismatch"]
    for key in ("kind", "source"):
        for value in sorted({case[key] for case in cases}):
            flags = [ok for case, ok in zip(cases, exact, strict=True) if case[key] == value]
            metrics[f"case_accuracy/{key}={value}"] = _share(flags)
            metrics[f"n/{key}={value}"] = float(len(flags))
    pairs = Counter((g[2], p[2]) for g, p in zip(gold, predictions, strict=True))
    for (true, pred), count in sorted(pairs.items()):
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
    cases = load_jsonl(path)
    metrics = evaluate(cases, [predict(case) for case in cases])
    result = write_result(COMPONENT, split, len(cases), metrics, note=NOTE)
    logger.info("localize (%s): n=%d", split, len(cases))
    for name in (
        "case_accuracy",
        "first_error_step_accuracy",
        "focus_step_accuracy",
        "error_type_accuracy",
        "mismatch_detection_rate",
    ):
        logger.info("  %-27s %.3f", name, metrics[name])
    for name in TYPES:
        logger.info("  %-27s support=%-4d recall=%.3f", name, metrics[f"support/{name}"],
                    metrics[f"recall/{name}"])  # fmt: skip
    for name, value in sorted(metrics.items()):
        if name.startswith("confusion/"):
            logger.info("  %s: %d", name, value)
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
