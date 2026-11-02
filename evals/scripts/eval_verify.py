"""Eval for `verify`: step-verdict accuracy on evals/datasets/<split>/verify_steps.jsonl.

Each case (`prev`, `curr`, optional `original`) is run through the real node: the problem is the
`original` when there is one (so `narrows` can be recognised), the pair is the last two steps, and
the verdict of `curr` is compared with the label. A check line (a closed statement) has relation
`equivalent` in the node, so a failed check is reported as `not_valid` here, as the dataset labels
it. Metrics are flat floats: overall accuracy, precision, recall and support per relation, accuracy
per source, and confusion counts.

What it does and does not cover: a single pair per case, so the multi-step logic (check lines,
unparsable lines in a chain, predecessor choice), `is_correct` and the justification claims are
tested only in tests/test_verify_node.py. Accuracy on these splits is high by construction; see
evals/datasets/README.md.

Chains (`chain/...`): evals/datasets/<split>/verify_chains.jsonl, when it exists, holds whole
hand-written solutions (definitions, reason lines, answers in a new letter). Every step's relation
is scored (`chain/step_accuracy`, recall per relation), and so is `is_correct`.
"""

import logging
from collections import Counter
from typing import Any

from evals.runner import dataset_path, load_jsonl, parse_split, setup_logging, write_result
from tutor.nodes.verify import verify
from tutor.state import Step, TutorState

COMPONENT = "verify"
NOTE = (
    "Accuracy is high by construction (mined positives were kept only where the checker agreed, "
    "negatives passed a witness check, hand-written labels were reconciled with the checker): a "
    "regression suite, not independent evidence. Single-pair cases only; is_correct is not "
    "evaluated. See evals/datasets/README.md and review/verify_build_report.json."
)
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
    if verdict.check_holds is False:
        return "not_valid"  # the dataset labels a false closed statement not_valid
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
        if predicted:  # precision is undefined, not 0, for a relation that was never predicted
            metrics[f"precision/{relation}"] = hits / predicted
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


def predict_chain(case: dict[str, Any]) -> tuple[list[str], bool]:
    """The relation of every step and `is_correct` for one chain."""
    steps = [Step(claim=step["claim"], kind=step["kind"]) for step in case["steps"]]
    result = verify({"problem": case["problem"], "student_steps": steps})
    relations = [
        "not_valid" if verdict.check_holds is False else str(verdict.relation)
        for verdict in result["step_verdicts"]
    ]
    return relations, bool(result["is_correct"])


def evaluate_chains(cases: list[dict[str, Any]]) -> dict[str, float]:
    """Step and `is_correct` accuracy over whole chains."""
    predictions = [predict_chain(case) for case in cases]
    pairs = [
        (true, pred)
        for case, (relations, _) in zip(cases, predictions, strict=True)
        for true, pred in zip(case["expected_relations"], relations, strict=True)
    ]
    metrics: dict[str, float] = {
        "chain/step_accuracy": sum(t == p for t, p in pairs) / len(pairs) if pairs else 0.0,
        "chain/chain_accuracy": sum(
            case["expected_relations"] == relations
            for case, (relations, _) in zip(cases, predictions, strict=True)
        )
        / len(cases),
        "chain/is_correct_accuracy": sum(
            case["expected_is_correct"] == correct
            for case, (_, correct) in zip(cases, predictions, strict=True)
        )
        / len(cases),
        "chain/n": float(len(cases)),
        "chain/n_steps": float(len(pairs)),
    }
    for relation in RELATIONS:
        support = sum(1 for true, _ in pairs if true == relation)
        if support:
            hits = sum(1 for true, pred in pairs if true == pred == relation)
            metrics[f"chain/recall/{relation}"] = hits / support
    for (true, pred), count in sorted(Counter(pairs).items()):
        if true != pred:
            metrics[f"chain/confusion/{true}->{pred}"] = float(count)
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
    chains_path = dataset_path(COMPONENT + "_chains", split)
    note = NOTE
    if chains_path.exists():
        chains = load_jsonl(chains_path)
        metrics.update(evaluate_chains(chains))
        note += f" Plus {len(chains)} hand-written chains (chain/...), labels spot-check pending."
    result = write_result(COMPONENT, split, len(cases), metrics, note=note)
    logger.info("%s (%s): n=%d accuracy=%.4f macro_recall=%.4f", COMPONENT, split, len(cases),
                metrics["accuracy"], metrics["macro_recall"])  # fmt: skip
    for relation in RELATIONS:
        precision = metrics.get(f"precision/{relation}")
        logger.info("  %-11s support=%-4d recall=%.3f precision=%s", relation,
                    metrics[f"support/{relation}"], metrics[f"recall/{relation}"],
                    "n/a" if precision is None else f"{precision:.3f}")  # fmt: skip
    for name in ("chain/step_accuracy", "chain/chain_accuracy", "chain/is_correct_accuracy"):
        if name in metrics:
            logger.info("  %-26s %.3f", name, metrics[name])
    for name, value in sorted(metrics.items()):
        if "confusion/" in name:
            logger.info("  %s: %d", name, value)
    logger.info("Wrote %s", result)


if __name__ == "__main__":
    main()
