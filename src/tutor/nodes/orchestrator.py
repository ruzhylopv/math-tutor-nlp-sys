"""Route the conversation. Three modes, chosen by `stage` (see docs/architecture.md).

new_message: an LLM `Decision` picks ask / diagnose / hint / reply; code guards the impossible
    choices (diagnose without steps, hint without a diagnosis) and counts the turn. A new problem
    (`topic` cleared by `parse_input` while a diagnosis of the old one is still stored) resets the
    per-problem fields.
diagnosed: plain code. Out-of-scope subject: decline. Clean solution: record the attempt, maybe
    offer practice. Otherwise set the hint level (different misconception: 1, same: +1) and hint.
hinted: plain code runs the leakage check, publishes the hint, or retries once, then falls back
    to the canned hint for the level. A rejected hint never enters `messages`.

Reads: messages, stage, and the state so far
Writes: next_action, hint_level, hint_retries, reply_text, messages, turns, hints_used,
        misconceptions_seen, learner_profile (and the per-problem fields on a reset)
Eval metric: routing accuracy on labelled turns
"""

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from tutor.config import ConfigError
from tutor.state import (
    IN_SCOPE_TOPICS,
    Decision,
    LearnerProfile,
    MisconceptionRecord,
    TutorState,
)
from tutor.tools import structured
from tutor.tools.canned_hints import MAX_LEVEL, canned_hint
from tutor.tools.catalogue import load_catalogue
from tutor.tools.diagnosis import is_clean_solution
from tutor.tools.leakage import find_leaks
from tutor.tools.learner_db import get_profile, learner_db_path, record_attempt

logger = logging.getLogger("tutor.orchestrator")

PRACTICE_THRESHOLD = 3  # the third occurrence of a misconception (scenario A)
MAX_RETRIES = 1  # one regeneration of a leaking hint, then the canned hint
ASK_TEXT = "Please write out your solution step by step, one line per step, so I can check it."
OUT_OF_SCOPE_TEXT = (
    "That looks like a topic outside school algebra, and I can only help with school algebra. "
    "Send me an algebra problem and your steps and I will gladly look at them."
)
CORRECT_TEXT = "Correct, well done!"


def _latest_student_message(state: TutorState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content.strip() if isinstance(message.content, str) else ""
    return ""


def _reply(text: str, action: str = "reply") -> dict[str, Any]:
    """Publish `text` to the student and end the run."""
    return {"next_action": action, "reply_text": text, "messages": [AIMessage(content=text)]}


def _db_path() -> str | None:
    try:
        return learner_db_path()
    except ConfigError:
        logger.warning("orchestrator: LEARNER_DB_PATH is not set; the learner DB is skipped")
        return None


def _fresh_problem_fields() -> dict[str, Any]:
    """Per-problem fields back to their starting values."""
    return {
        "hint_level": 1,
        "hint_retries": 0,
        "hints_used": 0,
        "turns": 0,
        "error_context": None,
        "misconception": None,
        "misconceptions_seen": [],
        "step_verdicts": [],
        "first_error_step": None,
        "focus_step": None,
    }


def _has_old_diagnosis(state: TutorState) -> bool:
    return bool(
        state.get("misconceptions_seen")
        or state.get("error_context") is not None
        or state.get("step_verdicts")
        or state.get("hints_used", 0) > 0
    )


def _decide(state: TutorState, message: str) -> Decision | None:
    steps = len(state.get("student_steps", []))
    diagnosed = "yes" if state.get("error_context") is not None else "no"
    text = (
        f"Student message: {message}\n"
        f"Stored problem: {state.get('problem') or 'none'}\n"
        f"Steps found in the message: {steps}\n"
        f"Diagnosis so far: {diagnosed}"
    )
    return structured.call_structured("orchestrator", Decision, text)


def _new_message(state: TutorState) -> dict[str, Any]:
    update: dict[str, Any] = {}
    # parse_input clears topic when the problem changes: drop what described the old problem
    if state.get("topic") is None and _has_old_diagnosis(state):
        update.update(_fresh_problem_fields())
    update["turns"] = update.get("turns", state.get("turns", 0)) + 1
    path = _db_path()
    if path is not None and "student_id" in state:
        update["learner_profile"] = get_profile(path, state["student_id"])

    has_steps = bool(state.get("student_steps")) and bool(state.get("problem"))
    # after a reset the old diagnosis is gone, so there is nothing to hint about
    can_hint = state.get("error_context") is not None and "error_context" not in update
    decision = _decide(state, _latest_student_message(state))
    if decision is None:
        logger.warning("orchestrator: no decision from the model; routing on the steps")
        action = "diagnose" if has_steps else "ask"
        text = None
    else:
        action, text = decision.action, decision.reply_text
    if action == "diagnose" and not has_steps:
        action = "ask"
    if action == "hint" and not can_hint:
        action = "ask"

    if action in ("ask", "reply"):
        update.update(_reply(text or (ASK_TEXT if action == "ask" else "Tell me more."), action))
        return update
    update["next_action"] = action
    if action == "hint":
        update["hint_level"] = min(state.get("hint_level", 1) + 1, MAX_LEVEL)
        update["hint_retries"] = 0
    return update


def _category(misconception_id: str) -> str:
    for entry in load_catalogue():
        if entry.id == misconception_id:
            return entry.category.replace("_", " ")
    return "this kind of mistake"


def _clean_solution(state: TutorState) -> dict[str, Any]:
    seen = state.get("misconceptions_seen", [])
    text = CORRECT_TEXT
    update: dict[str, Any] = {}
    path = _db_path()
    if path is not None and "student_id" in state:
        records = [MisconceptionRecord(misconception_id=i) for i in seen]
        record_attempt(
            path,
            state["student_id"],
            state.get("problem", ""),
            state.get("topic"),
            state.get("level"),
            state.get("turns", 0),
            state.get("hints_used", 0),
            True,
            records,
        )
        profile: LearnerProfile = get_profile(path, state["student_id"])
        update["learner_profile"] = profile
        for misconception_id in seen:
            if profile.misconception_counts.get(misconception_id, 0) >= PRACTICE_THRESHOLD:
                text += (
                    " You've made this kind of mistake a few times. Want a few practice "
                    f"problems on {_category(misconception_id)}?"
                )
                break
    update.update(_reply(text))
    update.update(_fresh_problem_fields())  # the attempt is finished
    return update


def _diagnosed(state: TutorState) -> dict[str, Any]:
    topic = state.get("topic")
    if topic is not None and topic not in IN_SCOPE_TOPICS:
        return _reply(OUT_OF_SCOPE_TEXT)
    if is_clean_solution(state):
        return _clean_solution(state)
    seen = list(state.get("misconceptions_seen", []))
    misconception = state.get("misconception")
    level = state.get("hint_level", 1)
    if misconception is None:
        # no misconception retrieved: escalate only if this problem already got a hint
        level = min(level + 1, MAX_LEVEL) if state.get("hints_used", 0) > 0 else 1
    else:
        same = bool(seen) and seen[-1] == misconception.id
        level = min(level + 1, MAX_LEVEL) if same else 1
        if misconception.id not in seen:
            seen.append(misconception.id)
    return {
        "next_action": "hint",
        "hint_level": level,
        "hint_retries": 0,
        "misconceptions_seen": seen,
    }


def _hinted(state: TutorState) -> dict[str, Any]:
    text = state.get("hint_text", "")
    level = state.get("hint_level", 1)
    context = state.get("error_context")
    before = context.before if context is not None else state.get("problem", "")
    leaks = find_leaks(text, state.get("problem", ""), before) if text else ["empty hint"]
    retries = state.get("hint_retries", 0)
    if leaks and retries < MAX_RETRIES:
        logger.info("orchestrator: hint leaks (%s); retrying", leaks)
        return {"next_action": "hint", "hint_retries": retries + 1}
    if leaks:
        logger.info("orchestrator: hint leaks twice (%s); using the canned hint", leaks)
        text = canned_hint(level)
    update = _reply(text)
    update["hints_used"] = state.get("hints_used", 0) + 1
    return update


def orchestrator(state: TutorState) -> dict[str, Any]:
    """Run the mode that `stage` selects (a missing stage means a new student message)."""
    stage = state.get("stage", "new_message")
    if stage == "diagnosed":
        return _diagnosed(state)
    if stage == "hinted":
        return _hinted(state)
    return _new_message(state)
