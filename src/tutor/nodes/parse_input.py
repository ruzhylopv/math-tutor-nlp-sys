"""Turn the student's latest message into the problem and the steps (plain-text math).

Runs on every message, before the orchestrator. It transcribes: it never solves, simplifies or
corrects. For a message without working it resets `student_steps` to an empty list (so steps from
the previous attempt are not mistaken for a new one); for a message without a problem it keeps the
stored `problem`. If there is no message, or the model fails twice, the steps are empty and the
problem stays. A problem that differs from the stored one also clears `topic` and `level`, which
described the old problem.

Reads: messages, problem
Writes: problem, student_steps, topic, level
Eval metric: problem-extraction accuracy; claim exact match; step-split accuracy; SymPy parse rate
"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from tutor.state import ParsedInput, TutorState
from tutor.tools import structured

logger = logging.getLogger("tutor.parse_input")


def _latest_student_message(state: TutorState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = message.content
            if isinstance(content, str):
                return content.strip()
            parts = (
                part if isinstance(part, str) else str(part.get("text", "")) for part in content
            )
            return " ".join(part for part in parts if part).strip()
    return ""


def parse_input(state: TutorState) -> dict[str, Any]:
    """Ask the model to split the latest message into a problem and steps."""
    message = _latest_student_message(state)
    if not message:
        return {"student_steps": []}
    stored = state.get("problem", "").strip() or "none"
    parsed = structured.call_structured(
        "parse_input", ParsedInput, f"Stored problem: {stored}\n\nStudent message:\n{message}"
    )
    if parsed is None:
        logger.warning("parse_input: no valid answer from the model; the message is not parsed")
        return {"student_steps": []}
    update: dict[str, Any] = {"student_steps": parsed.steps}
    if parsed.problem is not None and parsed.problem.strip():
        update["problem"] = parsed.problem.strip()
        if stored != "none" and update["problem"] != stored:
            update["topic"] = None
            update["level"] = None
    return update
