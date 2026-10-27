"""Eval for `hint`: answer leakage, counterexample use, and a rubric judge, on gold misconceptions.

Data: evals/datasets/<split>/hint.jsonl (built from the retrieve datasets by
`evals/builders/build_hint.py`). Each case is a wrong step with its true catalogue entry, so the
eval measures the hint and not `retrieve`; the state is built the way the graph builds it
(`finish_diagnosis` stores the wrong step) and `hint` runs on it with the case's level. Needs the
key in .env: one call for the hint and one for the judge. Answers are cached under
evals/.llm_cache.

Metrics: leakage rate (automatic, `tools/leakage`, overall and per level); canned rate (how often
the node fell back to the fixed hint); counterexample use (level 2, when the tool found numbers: the
hint contains both numbers); the judge's pass rates (praise, Socratic, on target, fits the level),
the judge's own leak rate, and how often the judge and the automatic check disagree on leaking.
`--limit N` takes N cases in turn over the levels. A sample of up to 20 hints is written beside the
result for the human check: fill `human_ok` and `human_note` by hand.

The judge is the same model that writes the hints, so it is lenient on itself; the human check is
the counterweight. The leakage check cannot see leaks it does not look for (see tools/leakage.py).
"""

import hashlib
import json
import logging
import os
from typing import Any

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
from tutor.nodes.finish_diagnosis import finish_diagnosis
from tutor.nodes.hint import hint
from tutor.state import ErrorContext, HintRubric, Misconception, Step, TutorState
from tutor.tools import structured
from tutor.tools.canned_hints import canned_hint
from tutor.tools.catalogue import load_catalogue
from tutor.tools.counterexample import counterexample
from tutor.tools.leakage import find_leaks

COMPONENT = "hint"
PROMPT = EVALS_DIR.parent / "src" / "tutor" / "prompts" / "hint.md"
SAMPLE_SIZE = 20
LEVELS = (1, 2, 3, 4)
CRITERIA = ("praises_correct_work", "socratic", "on_target", "fits_level")
logger = logging.getLogger("eval_hint")
NOTE = (
    "Gold misconception, one hint per case at the case's level. Cases are retrieve queries: mostly "
    "single-rule rewrites, easier than real student work. The judge is the same model that writes "
    "the hints (lenient on itself); leakage is the automatic check, which only sees what "
    "tools/leakage.py looks for. Quote with the human check, not alone."
)


def build_state(case: dict[str, Any]) -> tuple[TutorState, ErrorContext, Misconception]:
    """The state `hint` sees after a diagnosis of the case with the right misconception."""
    entry = next(e for e in load_catalogue() if e.id == case["expected"])
    state: TutorState = {
        "problem": case["problem"],
        "student_steps": [
            Step(claim=step["claim"], justification=step.get("justification", ""))
            for step in case["steps"]
        ],
        "focus_step": case["focus_step"],
    }
    context = finish_diagnosis(state)["error_context"]
    if context is None:
        raise ValueError(f"case {case['id']} has no usable focus step")
    misconception = Misconception(
        id=entry.id, description=entry.description, topic=entry.topic, score=1.0
    )
    state["error_context"] = context
    state["misconception"] = misconception
    state["hint_level"] = case["level"]
    return state, context, misconception


def judge_text(
    case: dict[str, Any], context: ErrorContext, misconception: Misconception, text: str
) -> str:
    return "\n".join(
        [
            f"Hint level: {case['level']}",
            f"Problem: {case['problem']}",
            f"Line before the wrong step: {context.before}",
            f"The student's wrong line: {context.after}",
            "Earlier lines that are correct: "
            + (" ; ".join(context.correct_steps) if context.correct_steps else "none"),
            f"Misconception: {misconception.description}",
            f"Hint to grade: {text}",
        ]
    )


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Generate the hint for a case and grade it."""
    state, context, misconception = build_state(case)
    text = hint(state)["hint_text"]
    found = counterexample(context.before, context.after, case["problem"])
    judge_input = judge_text(case, context, misconception, text)
    return {
        "id": case["id"],
        "level": case["level"],
        "source": case["source"],
        "hint_text": text,
        "canned": text == canned_hint(case["level"]),
        "leaks": find_leaks(text, case["problem"], context.before),
        "counterexample_available": case["level"] == 2 and found is not None,
        "counterexample_used": found is not None
        and found.before_value in text
        and found.after_value in text,
        "judge": structured.call_structured("hint_judge", HintRubric, judge_input),
        "wrong_line": context.after,
        "before": context.before,
    }


def _rate(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def evaluate(results: list[dict[str, Any]]) -> dict[str, float]:
    """All metrics for the per-case results of `run_case`."""
    judged = [r for r in results if r["judge"] is not None]
    metrics: dict[str, float] = {
        "leakage_rate": _rate([bool(r["leaks"]) for r in results]),
        "canned_rate": _rate([r["canned"] for r in results]),
        "judge_failure_rate": _rate([r["judge"] is None for r in results]),
        "judge_reveals_answer_rate": _rate([r["judge"].reveals_answer for r in judged]),
        "judge_vs_check_disagreement": _rate(
            [r["judge"].reveals_answer != bool(r["leaks"]) for r in judged]
        ),
    }
    available = [r for r in results if r["counterexample_available"]]
    metrics["counterexample_use_rate"] = _rate([r["counterexample_used"] for r in available])
    metrics["n/counterexample_available"] = float(len(available))
    for criterion in CRITERIA:
        metrics[f"judge_{criterion}"] = _rate([getattr(r["judge"], criterion) for r in judged])
    for level in LEVELS:
        subset = [r for r in results if r["level"] == level]
        judged_level = [r for r in subset if r["judge"] is not None]
        metrics[f"n/level={level}"] = float(len(subset))
        metrics[f"leakage_rate/level={level}"] = _rate([bool(r["leaks"]) for r in subset])
        for criterion in CRITERIA:
            metrics[f"judge_{criterion}/level={level}"] = _rate(
                [getattr(r["judge"], criterion) for r in judged_level]
            )
    metrics["n"] = float(len(results))
    return metrics


def sample_by_level(cases: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """`limit` cases taken in turn over the levels; deterministic (hash of the id)."""
    ordered = sorted(cases, key=lambda case: hashlib.sha256(case["id"].encode()).hexdigest())
    queues = [[case for case in ordered if case["level"] == level] for level in LEVELS]
    chosen: list[dict[str, Any]] = []
    while len(chosen) < limit and any(queues):
        for queue in queues:
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
    return sorted(chosen, key=lambda case: str(case["id"]))


def sample_rows(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Up to SAMPLE_SIZE hints, spread over the levels, for the developer's check by hand."""
    by_id = {r["id"]: r for r in results}
    picked = sample_by_level([{"id": r["id"], "level": r["level"]} for r in results], SAMPLE_SIZE)
    return [
        {
            "id": r["id"],
            "level": r["level"],
            "before": r["before"],
            "wrong_line": r["wrong_line"],
            "hint_text": r["hint_text"],
            "automatic_leaks": r["leaks"],
            "judge": r["judge"].model_dump() if r["judge"] else None,
            "human_ok": None,
            "human_note": "",
        }
        for r in (by_id[case["id"]] for case in picked)
    ]


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
    if limit is not None and limit < len(cases):
        note += f" SUBSET: {limit} of {len(cases)} cases, taken in turn over the levels."
        cases = sample_by_level(cases, limit)
    results = [run_case(case) for case in with_progress(cases, "hint")]
    metrics = evaluate(results)
    result = write_result(
        COMPONENT,
        split,
        len(cases),
        metrics,
        model_name=config.model_name,
        prompt_path=PROMPT,
        note=note,
    )
    samples = result.with_name(result.stem + "_samples.jsonl")
    samples.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sample_rows(results)),
        encoding="utf-8",
    )
    logger.info("hint (%s): n=%d", split, len(cases))
    logger.info(
        "  leakage=%.3f  canned=%.3f  counterexample_use=%.3f  judge_failures=%.3f",
        metrics["leakage_rate"],
        metrics["canned_rate"],
        metrics["counterexample_use_rate"],
        metrics["judge_failure_rate"],
    )
    logger.info("  judge  " + "  ".join(f"{c}={metrics[f'judge_{c}']:.3f}" for c in CRITERIA))
    logger.info("Wrote %s and %s", result, samples)


if __name__ == "__main__":
    main()
