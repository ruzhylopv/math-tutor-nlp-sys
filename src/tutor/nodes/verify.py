"""Check the final answer and each step with SymPy (equivalent / implies / not_valid / unparsable).

Reads: problem, student_steps
Writes: is_correct, step_verdicts
Eval metric: answer-check accuracy; step-verdict accuracy
"""

from typing import Any

from tutor.state import TutorState


def verify(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {"is_correct": False, "step_verdicts": []}  # TODO
