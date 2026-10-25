"""Write a Socratic hint grounded in the misconception, at the current hint level.

Reads: misconception, focus_step, hint_level, learner_profile, error_type,
       counterexample values from a SymPy tool (tool design still OPEN)
Writes: hint_text, stage
Eval metric: answer-leakage rate (automatic); rubric judge and a small human check
"""

from typing import Any

from tutor.state import TutorState


def hint(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {"hint_text": "TODO", "stage": "hinted"}  # TODO
