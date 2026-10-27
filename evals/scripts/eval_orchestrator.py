"""Eval for `orchestrator`: routing accuracy on labelled turns, and the scenario replays.

`--part routing` (default): evals/datasets/<split>/orchestrator.jsonl. Each case is one new student
message with the state the orchestrator sees (stored problem, number of parsed steps, whether a
diagnosis exists) and a hand-made `expected_action` (ask, diagnose, hint or reply). The real node
runs, so the guards are included. Needs the key in .env; answers are cached under evals/.llm_cache.
Metrics: routing accuracy, recall per action.

`--part scenarios`: replays evals/scenarios/*.yaml through the real graph and the real model
(slow on the free model: a turn with a diagnosis makes several calls). Metrics: turn pass rate
(visited nodes, hint level, reply text as the YAML expects), hint-level and leak rates over hint
turns, the share of expected misconceptions found, and hints given per scenario. The scenario
results go to evals/results/orchestrator_scenarios/.
"""

import argparse
import logging
import os
from collections import Counter
from typing import Any

from langchain_core.messages import HumanMessage

from evals.runner import (
    EVALS_DIR,
    SPLITS,
    dataset_path,
    load_jsonl,
    setup_logging,
    with_progress,
    write_result,
)
from evals.scenario_runner import ScenarioResult, load_scenario, replay, scenario_paths
from tutor.config import load_config
from tutor.nodes.orchestrator import orchestrator
from tutor.state import ErrorContext, Step, TutorState

COMPONENT = "orchestrator"
SCENARIO_COMPONENT = "orchestrator_scenarios"
PROMPT = EVALS_DIR.parent / "src" / "tutor" / "prompts" / "orchestrator.md"
ACTIONS = ("ask", "diagnose", "hint", "reply")
logger = logging.getLogger("eval_orchestrator")


def predict(case: dict[str, Any]) -> str:
    """The action the node picks for a case's message and context."""
    state: TutorState = {
        "messages": [HumanMessage(content=case["message"])],
        "student_steps": [Step(claim="x = 1") for _ in range(case["n_steps"])],
        "topic": "Algebra",
    }
    if case["problem"]:
        state["problem"] = case["problem"]
    if case["diagnosed"]:
        state["error_context"] = ErrorContext(
            step_number=1, before=case["problem"] or "", after="x = 1"
        )
    return str(orchestrator(state).get("next_action", "(none)"))


def evaluate_routing(cases: list[dict[str, Any]], predictions: list[str]) -> dict[str, float]:
    """Accuracy and per-action recall (with support) for the predicted actions."""
    expected = [case["expected_action"] for case in cases]
    pairs = list(zip(expected, predictions, strict=True))
    metrics: dict[str, float] = {"routing_accuracy": sum(t == p for t, p in pairs) / len(pairs)}
    for action in ACTIONS:
        support = sum(1 for t, _ in pairs if t == action)
        if support:
            metrics[f"support/{action}"] = float(support)
            metrics[f"recall/{action}"] = sum(1 for t, p in pairs if t == p == action) / support
    for (true, pred), count in sorted(Counter(pairs).items()):
        if true != pred:
            metrics[f"confusion/{true}->{pred}"] = float(count)
    return metrics


def evaluate_scenarios(results: list[ScenarioResult]) -> dict[str, float]:
    """Pass and leak rates over all turns of the replayed scenarios."""
    turns = [turn for result in results for turn in result.turns]
    hint_turns = [turn for turn in turns if turn.hint_level is not None]
    graded = [turn for turn in turns if turn.misconception_ok is not None]
    metrics: dict[str, float] = {
        "turn_pass_rate": sum(not turn.failures for turn in turns) / len(turns),
        "leak_rate": sum(bool(turn.leaks) for turn in hint_turns) / len(hint_turns)
        if hint_turns
        else 0.0,
        "misconception_match_rate": sum(bool(turn.misconception_ok) for turn in graded)
        / len(graded)
        if graded
        else 0.0,
    }
    for result in results:
        metrics[f"hints_given/{result.name}"] = float(result.hints_given)
        metrics[f"turns_passed/{result.name}"] = float(sum(not t.failures for t in result.turns))
    return metrics


def _run_routing(split: str) -> None:
    path = dataset_path(COMPONENT, split)
    if not path.exists():
        logger.info("Dataset %s is missing. No labels are invented; add the dataset first.", path)
        return
    os.environ.setdefault("LLM_CACHE_DIR", str(EVALS_DIR / ".llm_cache"))
    config = load_config()
    cases = load_jsonl(path)
    predictions = [predict(case) for case in with_progress(cases, "orchestrator")]
    metrics = evaluate_routing(cases, predictions)
    result = write_result(
        COMPONENT, split, len(cases), metrics, model_name=config.model_name, prompt_path=PROMPT
    )
    logger.info("orchestrator routing (%s): n=%d", split, len(cases))
    for name, value in metrics.items():
        logger.info("  %s: %.3f", name, value)
    logger.info("Wrote %s", result)


def _run_scenarios(split: str) -> None:
    os.environ.setdefault("LLM_CACHE_DIR", str(EVALS_DIR / ".llm_cache"))
    config = load_config()
    paths = scenario_paths()
    results = [replay(load_scenario(path)) for path in with_progress(paths, "scenario")]
    metrics = evaluate_scenarios(results)
    for result in results:
        for number, turn in enumerate(result.turns, 1):
            for failure in turn.failures:
                logger.info("  %s turn %d: %s", result.name, number, failure)
    out = write_result(
        SCENARIO_COMPONENT,
        split,
        sum(len(r.turns) for r in results),
        metrics,
        model_name=config.model_name,
        prompt_path=PROMPT,
        note="Live replay of evals/scenarios/*.yaml; n_examples counts turns, not scenarios.",
    )
    for name, value in metrics.items():
        logger.info("  %s: %.3f", name, value)
    logger.info("Wrote %s", out)


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SPLITS, default="dev")
    parser.add_argument("--part", choices=("routing", "scenarios"), default="routing")
    args = parser.parse_args()
    if args.part == "routing":
        _run_routing(args.split)
    else:
        _run_scenarios(args.split)


if __name__ == "__main__":
    main()
