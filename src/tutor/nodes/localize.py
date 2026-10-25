"""Find the first wrong step, the step to talk about, and the error type.

Reads: step_verdicts, student_steps, is_correct
Writes: first_error_step, focus_step, error_type
Eval metric: first-error-step accuracy; error-type accuracy; mismatch detection rate
"""

from typing import Any

from tutor.state import TutorState


def localize(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {
        "first_error_step": None,
        "focus_step": None,
        "error_type": "algebraic_transformation",
    }  # TODO
