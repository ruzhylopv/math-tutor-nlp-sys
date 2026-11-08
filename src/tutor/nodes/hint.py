"""Write a Socratic hint grounded in the misconception, at the current hint level.

Reads the wrong step from `error_context` (copied at diagnosis time), not from `student_steps`,
which `parse_input` may have cleared. The model words the hint; the numbers of a counterexample
(level 2) come from SymPy (`tools/counterexample`) and the model never computes. Level 4 is the
only one that is given the catalogue's general rule. Without an `error_context`, or when the model
fails, the hint is the canned one for the level, so the node always returns a hint. The leakage
check, the retry and the level changes belong to the orchestrator.

A student with a stored problem and no working yet (`is_no_working_help`) gets one guiding question
about how to begin, with no judgement of their math unless they are replying to that question.

With `error_type` `incomplete` nothing is wrong: the student stopped before an answer, so the model
is told that the work is correct and given the last valid line, with no counterexample or rule.
With intent `answer` the model also gets the tutor's last message and the reply, responds to the
reply first and judges whether it moves forward; a failed call gives no verdict. This is the one
place where the LLM judges a student's math (see CLAUDE.md); submitted steps still go to SymPy.

Reads: error_context, error_type, misconception, hint_level, problem, intent, messages
Writes: hint_text, stage, reply_moves_forward (only for intent `answer`)
Eval metric: answer-leakage rate (automatic); rubric judge and a small human check
"""

import logging
from typing import Any

from tutor.state import ErrorContext, HintText, Misconception, TutorState
from tutor.tools import structured
from tutor.tools.canned_hints import MAX_LEVEL, NO_WORKING, canned_hint
from tutor.tools.catalogue import load_catalogue
from tutor.tools.counterexample import counterexample
from tutor.tools.diagnosis import is_no_working_help
from tutor.tools.messages import conversation_text, last_tutor_message, latest_student_message

logger = logging.getLogger("tutor.hint")


def _correct_rule(misconception: Misconception) -> str | None:
    for entry in load_catalogue():
        if entry.id == misconception.id:
            return entry.correct_rule
    return None


def _stopped_lines(state: TutorState, context: ErrorContext, level: int) -> list[str]:
    return [
        f"Hint level: {level}",
        f"Problem: {state.get('problem', '')}",
        "Situation: every line so far is correct, but there is no final answer yet.",
        f"The student's last valid line: {context.after}",
        "Earlier lines that are correct: "
        + (" ; ".join(context.correct_steps) if context.correct_steps else "none"),
        f"Student says they are stuck: {'yes' if state.get('intent') == 'stuck' else 'no'}",
    ]


def _mistake_lines(state: TutorState, context: ErrorContext, level: int) -> list[str]:
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
    return lines


def _no_working_lines(state: TutorState, level: int) -> list[str]:
    lines = [
        f"Hint level: {level}",
        f"Problem: {state.get('problem', '')}",
        "Starting point: the student has not written any working yet and wants help to begin.",
    ]
    if state.get("intent") != "answer":
        lines.append(f"Student's message: {latest_student_message(state)}")
    return lines


def _prompt_text(state: TutorState, context: ErrorContext | None, level: int) -> str:
    if context is None:
        lines = _no_working_lines(state, level)
    elif state.get("error_type") == "incomplete":
        lines = _stopped_lines(state, context, level)
    else:
        lines = _mistake_lines(state, context, level)
    if state.get("intent") == "answer":
        lines.append(f"Tutor's last message: {last_tutor_message(state) or 'none'}")
        lines.append(f"Student's reply: {latest_student_message(state)}")
    conversation = conversation_text(state)
    if conversation:
        lines.append(f"Conversation so far:\n{conversation}")
    return "\n".join(lines)


def hint(state: TutorState) -> dict[str, Any]:
    """Word one hint for the focus step at the current hint level."""
    level = min(max(state.get("hint_level", 1), 1), MAX_LEVEL)
    is_reply = state.get("intent") == "answer"
    context = state.get("error_context")
    no_working = is_no_working_help(state)
    kind = NO_WORKING if no_working else state.get("error_type")
    update: dict[str, Any] = {"stage": "hinted"}
    if is_reply:
        update["reply_moves_forward"] = None
    if context is None and not no_working:
        logger.warning("hint: no error context; using the canned hint for level %d", level)
        return {**update, "hint_text": canned_hint(level, kind)}
    result = structured.call_structured("hint", HintText, _prompt_text(state, context, level))
    text = result.text.strip() if result else ""
    if not text:
        logger.warning("hint: no usable answer from the model; using the canned hint")
        text = canned_hint(level, kind)
    elif is_reply and result is not None:
        update["reply_moves_forward"] = result.reply_moves_forward
    return {**update, "hint_text": text}
