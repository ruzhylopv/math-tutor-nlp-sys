"""Turn the student's raw message into the problem text and the attempt as Steps.

Reads: messages, problem
Writes: problem, student_steps
Eval metric: problem-extraction accuracy; step-split accuracy; SymPy parse rate of claims
"""

from typing import Any

from tutor.state import TutorState


def parse_input(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {"problem": state.get("problem", ""), "student_steps": []}  # TODO
