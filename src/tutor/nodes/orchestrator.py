"""Route the conversation. Three modes, chosen by `stage` (see docs/architecture.md).

new_message: an LLM `Decision` picks ask / diagnose / hint / reply; code guards the impossible
    choices (diagnose without steps, hint without a diagnosis) and counts the turn. A reply to
    the tutor when a diagnosis exists is routed by code, with no
    model call: with a line of math to `diagnose` (SymPy checks it), otherwise to `hint`, and the
    level stays for its own hint. A line using a letter that is not in the problem also goes to
    `hint`, because definitions from an earlier turn are not known to `verify` (a known limit).
    A student with a stored problem and no working may also get a `hint`, to help them begin; its
    first one is level 1, and an out-of-scope subject is declined instead. A clarifying question
    after any hint keeps the level. Code overrules an `ask` or `reply` from the model for such a
    student, because the model's `reply_text` does not pass the hint rules or the leakage check.
    Code also overrules a `hint` after a diagnosis when the message brings new working that
    `verify` can check: it goes to `diagnose`, so a hint is never built on a stale wrong line.
diagnosed: plain code. Out-of-scope subject: decline. Clean solution: record the attempt, maybe
    offer practice. Otherwise set the hint level (different misconception: 1, same: +1; partial
    progress keeps it unless the student is stuck) and hint. A reply keeps the level for its own
    hint, also when it contains math.
hinted: plain code runs the leakage check, publishes the hint, or retries once, then falls back
    to the canned hint for the level. A rejected hint never enters `messages`. A reply the hint
    judged as not moving forward raises the level for the next hint. For a stopped solution the
    last valid line may be quoted, so the line derived from it is what the check flags.

Reads: messages, stage, intent, reply_moves_forward, and the state so far
Writes: next_action, decision_reason, stage (when routing to `diagnose`), error_context,
        hint_level, hint_retries, reply_text, messages, turns, hints_used, misconceptions_seen,
        learner_profile (and the per-problem fields after a clean solution)
Eval metric: routing accuracy on labelled turns
"""

import logging
from typing import Any

from langchain_core.messages import AIMessage

from tutor.config import ConfigError
from tutor.state import (
    IN_SCOPE_TOPICS,
    Decision,
    LearnerProfile,
    MisconceptionRecord,
    TutorState,
)
from tutor.tools import structured
from tutor.tools.algebra import is_closed_statement
from tutor.tools.canned_hints import MAX_LEVEL, NO_WORKING, canned_hint
from tutor.tools.catalogue import load_catalogue
from tutor.tools.diagnosis import (
    error_context,
    fresh_problem_fields,
    is_calculation_reply,
    is_clean_solution,
    is_hint_reply,
    is_no_working_help,
    no_diagnosis_yet,
    uses_new_letter,
)
from tutor.tools.leakage import find_leaks
from tutor.tools.learner_db import get_profile, learner_db_path, record_attempt
from tutor.tools.messages import conversation_text, last_tutor_message, latest_student_message

logger = logging.getLogger("tutor.orchestrator")

PRACTICE_THRESHOLD = 3  # the third occurrence of a misconception (scenario A)
MAX_RETRIES = 1  # one regeneration of a leaking hint, then the canned hint
ASK_TEXT = "Please write out your solution step by step, one line per step, so I can check it."
OUT_OF_SCOPE_TEXT = (
    "That looks like a topic outside school algebra, and I can only help with school algebra. "
    "Send me an algebra problem and your steps and I will gladly look at them."
)
CORRECT_TEXT = "Correct, well done!"


def _reply(text: str, action: str = "reply") -> dict[str, Any]:
    """Publish `text` to the student and end the run."""
    return {"next_action": action, "reply_text": text, "messages": [AIMessage(content=text)]}


def _db_path() -> str | None:
    try:
        return learner_db_path()
    except ConfigError:
        logger.warning("orchestrator: LEARNER_DB_PATH is not set; the learner DB is skipped")
        return None


def _decide(state: TutorState, message: str) -> Decision | None:
    steps = len(state.get("student_steps", []))
    diagnosed = "yes" if state.get("error_context") is not None else "no"
    text = (
        f"Student message: {message}\n"
        f"Stored problem: {state.get('problem') or 'none'}\n"
        f"Steps found in the message: {steps}\n"
        f"Diagnosis so far: {diagnosed}\n"
        f"Student intent: {state.get('intent') or 'other'}\n"
        f"Tutor's last message: {last_tutor_message(state) or 'none'}\n"
        f"Conversation so far:\n{conversation_text(state) or 'none'}"
    )
    return structured.call_structured("orchestrator", Decision, text)


def _out_of_scope(state: TutorState) -> bool:
    topic = state.get("topic")
    return topic is not None and topic not in IN_SCOPE_TOPICS


def _next_hint_level(state: TutorState, diagnosed: bool) -> int:
    """One level up, except that help before any working starts at 1, and a clarifying question
    after a hint keeps the level: not following the tutor is no reason to give more away."""
    level = state.get("hint_level", 1)
    hinted = state.get("hints_used", 0) > 0
    if hinted and state.get("intent") == "explain":
        return level
    if not diagnosed and not hinted:
        return 1
    return min(level + 1, MAX_LEVEL)


def _has_checkable_working(state: TutorState) -> bool:
    """Lines `verify` can compare with the problem: not only plain calculations (those keep the
    earlier diagnosis) and no letter that is not in the problem (`verify` does not know it)."""
    steps = state.get("student_steps", [])
    has_working = any(not is_closed_statement(step.claim) for step in steps)
    return has_working and not uses_new_letter(state)


def _new_message(state: TutorState) -> dict[str, Any]:
    update: dict[str, Any] = {"turns": state.get("turns", 0) + 1}
    path = _db_path()
    if path is not None and "student_id" in state:
        update["learner_profile"] = get_profile(path, state["student_id"])

    has_steps = bool(state.get("student_steps")) and bool(state.get("problem"))
    diagnosed = state.get("error_context") is not None
    can_hint = diagnosed or is_no_working_help(state)
    # with no diagnosis, only a reply to an earlier hint skips the model: `answer` may also be
    # the student handing over the problem the tutor asked for
    is_reply = is_hint_reply(state) and (diagnosed or no_diagnosis_yet(state))
    decision = None if is_reply else _decide(state, latest_student_message(state))
    text = None
    if is_reply:
        action = "diagnose" if has_steps and not uses_new_letter(state) else "hint"
    elif decision is None:
        logger.warning("orchestrator: no decision from the model; routing on the steps")
        action = "diagnose" if has_steps else "ask"
    else:
        action, text = decision.action, decision.reply_text
    if action == "hint" and diagnosed and has_steps and _has_checkable_working(state):
        action = "diagnose"  # the stored diagnosis is about older lines than these
    if action == "diagnose" and not has_steps:
        action = "ask"
    if action == "hint" and not can_hint:
        action = "ask"
    wants_help = not has_steps and state.get("intent") in ("stuck", "explain")
    if action in ("ask", "reply") and wants_help and can_hint and not diagnosed:
        action, text = "hint", None  # the model's own text would skip the hint rules and the check

    if action == "hint" and not diagnosed and _out_of_scope(state):
        update.update(_reply(OUT_OF_SCOPE_TEXT))
        return update

    if decision is not None and action == decision.action:  # code may have overruled the model
        update["decision_reason"] = decision.reason
    if action in ("ask", "reply"):
        update.update(_reply(text or (ASK_TEXT if action == "ask" else "Tell me more."), action))
        return update
    update["next_action"] = action
    if action == "diagnose":
        update["stage"] = "diagnosed"  # the diagnosis subgraph returns here in this mode
    if action == "hint":
        if not is_reply:  # a reply's own hint keeps the level; `_hinted` applies its verdict
            update["hint_level"] = _next_hint_level(state, diagnosed)
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
    # the attempt is finished; `is_correct` stays so a follow-up is not taken for no working yet
    update.update({**fresh_problem_fields(), "is_correct": True})
    return update


def _diagnosed(state: TutorState) -> dict[str, Any]:
    if _out_of_scope(state):
        return {**_reply(OUT_OF_SCOPE_TEXT), "error_context": None}
    if is_clean_solution(state):
        return _clean_solution(state)
    if is_calculation_reply(state):  # the earlier diagnosis and the level stand
        return {"next_action": "hint", "hint_retries": 0}
    seen = list(state.get("misconceptions_seen", []))
    misconception = state.get("misconception")
    level = state.get("hint_level", 1)
    if misconception is None:
        # no misconception retrieved: escalate only if this problem already got a hint, and
        # not for partial progress unless the student says they are stuck
        progress = state.get("error_type") == "incomplete" and state.get("intent") != "stuck"
        if state.get("hints_used", 0) == 0:
            level = 1
        elif not progress:
            level = min(level + 1, MAX_LEVEL)
    else:
        same = bool(seen) and seen[-1] == misconception.id
        level = min(level + 1, MAX_LEVEL) if same else 1
        if misconception.id not in seen:
            seen.append(misconception.id)
    if state.get("intent") == "answer":  # a reply's own hint keeps the level; `_hinted` raises it
        level = state.get("hint_level", 1)
    return {
        "next_action": "hint",
        "hint_level": level,
        "hint_retries": 0,
        "misconceptions_seen": seen,
        "error_context": error_context(state),
    }


def _hinted(state: TutorState) -> dict[str, Any]:
    text = state.get("hint_text", "")
    level = state.get("hint_level", 1)
    context = state.get("error_context")
    stopped = state.get("error_type") == "incomplete"
    if context is None:
        before = state.get("problem", "")
    else:
        before = context.after if stopped else context.before
    no_working = is_no_working_help(state)
    leaks = (
        find_leaks(text, state.get("problem", ""), before, named_solutions=no_working)
        if text
        else ["empty hint"]
    )
    retries = state.get("hint_retries", 0)
    if leaks and retries < MAX_RETRIES:
        logger.info("orchestrator: hint leaks (%s); retrying", leaks)
        return {"next_action": "hint", "hint_retries": retries + 1}
    if leaks:
        logger.info("orchestrator: hint leaks twice (%s); using the canned hint", leaks)
        kind = NO_WORKING if no_working else state.get("error_type")
        text = canned_hint(level, kind)
    update = _reply(text)
    update["hints_used"] = state.get("hints_used", 0) + 1
    if is_hint_reply(state) and state.get("reply_moves_forward") is False:
        update["hint_level"] = min(level + 1, MAX_LEVEL)
    return update


def orchestrator(state: TutorState) -> dict[str, Any]:
    """Run the mode that `stage` selects (a missing stage means a new student message)."""
    stage = state.get("stage", "new_message")
    if stage == "diagnosed":
        return _diagnosed(state)
    if stage == "hinted":
        return _hinted(state)
    return _new_message(state)
