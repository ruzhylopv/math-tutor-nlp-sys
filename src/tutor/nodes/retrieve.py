"""Search the misconception catalogue for the misconception behind the wrong step.

Reads: problem, focus_step, topic, error_type
Writes: misconception_candidates, misconception
Eval metric: Recall@k; MAP@k
"""

from typing import Any

from tutor.state import TutorState


def retrieve(state: TutorState) -> dict[str, Any]:
    """Stub: returns fixed placeholder values (see the module docstring)."""
    return {"misconception_candidates": [], "misconception": None}  # TODO
