"""Route the conversation. Three modes, chosen by `stage` (see docs/architecture.md).

new_message: an LLM `Decision` picks ask / diagnose / hint / reply.
diagnosed: plain code sets the hint level, or records the attempt when the solution is clean.
hinted: plain code runs the leakage check, publishes the hint, or retries once.

Reads: messages, stage, and the state so far
Writes: next_action, hint_level, hint_retries, reply_text, messages, turns, hints_used,
        misconceptions_seen, learner_profile
Eval metric: routing accuracy on labelled turns
"""

from typing import Any

from tutor.state import TutorState


def orchestrator(state: TutorState) -> dict[str, Any]:
    """Stub: always replies with a placeholder (see the module docstring)."""
    return {"next_action": "reply", "reply_text": "TODO"}  # TODO
