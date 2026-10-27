"""Search the misconception catalogue for the misconception behind the wrong step.

The search compares the shape of the rewrite from the line before the focus step to the line the
student wrote there (see `tutor.tools.retrieval`). The top 5 matches go to
`misconception_candidates` and the best one to `misconception`. With nothing to look for (no focus
step, or an error type of None or `other`) both are empty. No score threshold yet
(docs/plans/nodes/2026-10-27-m4b-retrieve.md).

Reads: problem, student_steps, focus_step, error_type
Writes: misconception_candidates, misconception
Eval metric: Recall@k; MAP@k
"""

from typing import Any

from tutor.state import TutorState
from tutor.tools import retrieval

TOP_K = 5


def focus_lines(state: TutorState) -> tuple[str, str] | None:
    """(the line before the focus step, the line written at it), or None if nothing to look for."""
    focus = state.get("focus_step")
    steps = state.get("student_steps", [])
    if state.get("error_type") in (None, "other") or focus is None or not 1 <= focus <= len(steps):
        return None
    previous = state.get("problem", "") if focus == 1 else steps[focus - 2].claim
    return previous, steps[focus - 1].claim


def retrieve(state: TutorState) -> dict[str, Any]:
    """Look the focus step up in the catalogue."""
    lines = focus_lines(state)
    candidates = retrieval.search(*lines, k=TOP_K) if lines else []
    return {
        "misconception_candidates": candidates,
        "misconception": candidates[0] if candidates else None,
    }
