"""Tag the topic and the difficulty level of the problem.

Reads: problem, student_steps
Writes: topic, level
Eval metric: topic accuracy / macro-F1
"""

from typing import Any

from tutor.state import TutorState


def classify(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {"topic": "TODO", "level": 1}  # TODO
