"""Last node of the diagnosis subgraph: mark the diagnosis as finished and keep the wrong step.

The wrong step is copied into `error_context` here, because `parse_input` clears `student_steps` on
the next message without working and `hint` still needs it. A clean solution (no focus step) resets
it to None, so a context from an earlier diagnosis cannot survive.

Reads: problem, student_steps, focus_step
Writes: stage, error_context
Eval metric: none (exempt from the eval-script rule; unit tests only)
"""

from typing import Any

from tutor.state import ErrorContext, TutorState


def _error_context(state: TutorState) -> ErrorContext | None:
    focus = state.get("focus_step")
    steps = state.get("student_steps", [])
    if focus is None or not 1 <= focus <= len(steps):
        return None
    before = state.get("problem", "") if focus == 1 else steps[focus - 2].claim
    return ErrorContext(
        step_number=focus,
        before=before,
        after=steps[focus - 1].claim,
        correct_steps=[step.claim for step in steps[: focus - 1]],
    )


def finish_diagnosis(state: TutorState) -> dict[str, Any]:
    """Mark the diagnosis as finished and store the wrong step."""
    return {"stage": "diagnosed", "error_context": _error_context(state)}
