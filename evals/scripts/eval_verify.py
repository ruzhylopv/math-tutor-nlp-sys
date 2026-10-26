"""Eval for `verify`: step-verdict accuracy on evals/datasets/<split>/verify_steps.jsonl.

Each case (`prev`, `curr`, optional `original`) is run through the real node: the problem is the
`original` when there is one (so `narrows` can be recognised), the pair is the last two steps, and
the verdict of `curr` is compared with the label. Metrics are flat floats: overall accuracy,
precision, recall and support per relation, accuracy per source, and confusion counts.
"""

import logging
from collections import Counter
from typing import Any

from evals.runner import dataset_path, load_jsonl, parse_split, setup_logging, write_result
from tutor.nodes.verify import verify
from tutor.state import Step, TutorState

COMPONENT = "verify"
RELATIONS = ("equivalent", "implies", "narrows", "not_valid", "unparsable")
logger = logging.getLogger("eval_verify")


def predict(case: dict[str, Any]) -> str:
    """The relation the node gives to `curr`."""
    if case.get("original"):
        state: TutorState = {
            "problem": case["original"],
            "student_steps": [Step(claim=case["prev"]), Step(claim=case["curr"])],
        }
        verdict = verify(state)["step_verdicts"][1]
    else:
        state = {"problem": case["prev"], "student_steps": [Step(claim=case["curr"])]}
        verdict = verify(state)["step_verdicts"][0]
    return str(verdict.relation)


def evaluate(cases: list[dict[str, Any]]) -> dict[str, float]:
    """All metrics for a list of labelled cases."""
    predictions = [(case["relation"], predict(case), case["source"]) for case in cases]
    metrics: dict[str, float] = {"accuracy": _share(predictions, lambda t, p, s: t == p)}
    for relation in RELATIONS:
        support = sum(1 for true, _, _ in predictions if true == relation)
        predicted = sum(1 for _, pred, _ in predictions if pred == relation)
        hits = sum(1 for true, pred, _ in predictions if true == pred == relation)
        metrics[f"support/{relation}"] = float(support)
        metrics[f"recall/{relation}"] = hits / support if support else 0.0
        metrics[f"precision/{relation}"] = hits / predicted if predicted else 0.0
    recalls = [metrics[f"recall/{r}"] for r in RELATIONS if metrics[f"support/{r}"]]
    metrics["macro_recall"] = sum(recalls) / len(recalls) if recalls else 0.0
    for source in sorted({source for _, _, source in predictions}):
        subset = [item for item in predictions if item[2] == source]
        metrics[f"accuracy/source={source}"] = _share(subset, lambda t, p, s: t == p)
        metrics[f"n/source={source}"] = float(len(subset))
    for (true, pred), count in sorted(Counter((t, p) for t, p, _ in predictions).items()):
        if true != pred:
            metrics[f"confusion/{true}->{pred}"] = float(count)
    return metrics


def _share(items: list[tuple[str, str, str]], keep: Any) -> float:
    return sum(1 for item in items if keep(*item)) / len(items) if items else 0.0


def main() -> None:
    setup_logging()
    split = parse_split(__doc__)
    path = dataset_path(COMPONENT + "_steps", split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    cases = load_jsonl(path)
    metrics = evaluate(cases)
    result = write_result(COMPONENT, split, len(cases), metrics)
    logger.info("%s (%s): n=%d accuracy=%.4f macro_recall=%.4f", COMPONENT, split, len(cases),
                metrics["accuracy"], metrics["macro_recall"])  # fmt: skip
    for relation in RELATIONS:
        logger.info("  %-11s support=%-4d recall=%.3f precision=%.3f", relation,
                    metrics[f"support/{relation}"], metrics[f"recall/{relation}"],
                    metrics[f"precision/{relation}"])  # fmt: skip
    for name, value in sorted(metrics.items()):
        if name.startswith("confusion/"):
            logger.info("  %s: %d", name, value)
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
