"""Write a Socratic hint grounded in the misconception, at the current hint level.

Reads the wrong step from `error_context` (copied at diagnosis time), not from `student_steps`,
which `parse_input` may have cleared. The model words the hint; the numbers of a counterexample
(level 2) come from SymPy (`tools/counterexample`) and the model never computes. Level 4 is the
only one that is given the catalogue's general rule. Without an `error_context`, or when the model
fails, the hint is the canned one for the level, so the node always returns a hint. The leakage
check, the retry and the level changes belong to the orchestrator.

Reads: error_context, misconception, hint_level, problem
Writes: hint_text, stage
Eval metric: answer-leakage rate (automatic); rubric judge and a small human check
"""

import logging
from typing import Any

from tutor.state import ErrorContext, HintText, Misconception, TutorState
from tutor.tools import structured
from tutor.tools.canned_hints import MAX_LEVEL, canned_hint
from tutor.tools.catalogue import load_catalogue
from tutor.tools.counterexample import counterexample

logger = logging.getLogger("tutor.hint")


def _correct_rule(misconception: Misconception) -> str | None:
    for entry in load_catalogue():
        if entry.id == misconception.id:
            return entry.correct_rule
    return None


def _prompt_text(state: TutorState, context: ErrorContext, level: int) -> str:
    problem = state.get("problem", "")
    misconception = state.get("misconception")
    lines = [
        f"Hint level: {level}",
        f"Problem: {problem}",
        f"Step {context.step_number} is the wrong step.",
        f"Line before the wrong step: {context.before}",
        f"The student's wrong line: {context.after}",
        "Earlier lines that are correct: "
        + (" ; ".join(context.correct_steps) if context.correct_steps else "none"),
        "Misconception: " + (misconception.description if misconception else "unknown"),
    ]
    if level == 2:
        found = counterexample(context.before, context.after, problem)
        lines.append("Counterexample: " + (found.describe() if found else "none available"))
    if level == MAX_LEVEL and misconception is not None:
        rule = _correct_rule(misconception)
        if rule:
            lines.append(f"General rule you may state: {rule}")
    return "\n".join(lines)


def hint(state: TutorState) -> dict[str, Any]:
    """Word one hint for the wrong step at the current hint level."""
    level = min(max(state.get("hint_level", 1), 1), MAX_LEVEL)
    context = state.get("error_context")
    if context is None:
        logger.warning("hint: no error context; using the canned hint for level %d", level)
        return {"hint_text": canned_hint(level), "stage": "hinted"}
    result = structured.call_structured("hint", HintText, _prompt_text(state, context, level))
    text = result.text.strip() if result else ""
    if not text:
        logger.warning("hint: no usable answer from the model; using the canned hint")
        text = canned_hint(level)
    return {"hint_text": text, "stage": "hinted"}
