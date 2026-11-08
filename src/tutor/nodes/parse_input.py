"""Turn the student's latest message into the problem, the steps, the intent and the topic.

Runs on every message, before the orchestrator. It transcribes: it never solves, simplifies or
corrects. Each step gets a `kind` (equation, definition, reason, check, other), and the message an
`intent`; the tutor's last message is passed in so a reply to its question can be recognised.
For a message without working it resets `student_steps` to an empty list (so steps from the
previous attempt are not mistaken for a new one); for a message without a problem it keeps the
stored `problem`, `topic` and `level`. If there is no message, or the model fails twice, the steps
are empty and the rest stays. A stated problem with a topic from the model sets `topic` and
`level`; a problem that differs from the stored one and has no topic clears them, since they
described the old problem.

Reads: messages, problem
Writes: problem, student_steps, intent, topic, level
Eval metric: problem-extraction accuracy; claim exact match; step-split accuracy; SymPy parse rate;
    kind accuracy; intent accuracy; topic accuracy / macro-F1
"""

import logging
from typing import Any

from tutor.state import ParsedInput, TutorState
from tutor.tools import structured
from tutor.tools.messages import last_tutor_message, latest_student_message

logger = logging.getLogger("tutor.parse_input")


def _squash(text: str) -> str:
    """Remove all whitespace, so `3x=9` and `3x = 9` count as the same problem."""
    return "".join(text.split())


def parse_input(state: TutorState) -> dict[str, Any]:
    """Ask the model to split the latest message into a problem, steps, intent and topic."""
    message = latest_student_message(state)
    if not message:
        return {"student_steps": []}
    stored = state.get("problem", "").strip() or "none"
    tutor = last_tutor_message(state) or "none"
    text = f"Stored problem: {stored}\n\nTutor's last message:\n{tutor}\n\nStudent message:\n"
    parsed = structured.call_structured("parse_input", ParsedInput, text + message)
    if parsed is None:
        logger.warning("parse_input: no valid answer from the model; the message is not parsed")
        return {"student_steps": []}
    update: dict[str, Any] = {"student_steps": parsed.steps, "intent": parsed.intent}
    if parsed.problem is not None and parsed.problem.strip():
        update["problem"] = parsed.problem.strip()
        if parsed.topic is not None:
            update["topic"] = parsed.topic
            update["level"] = parsed.level
        elif stored != "none" and _squash(update["problem"]) != _squash(stored):
            update["topic"] = None
            update["level"] = None
    return update
