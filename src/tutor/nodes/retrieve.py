"""Search the misconception catalogue for the misconception behind the wrong step.

The search compares the shape of the rewrite from the line before the focus step to the line the
student wrote there (see `tutor.tools.retrieval`). The top 5 matches go to
`misconception_candidates`. The best one becomes `misconception` only if its score reaches
`MIN_SCORE`; below it the node abstains (`misconception` is None) and `hint` writes a generic hint.
With nothing to look for (no focus step, or an error type of None or `other`) both are empty.
`MIN_SCORE` was chosen on the dev split (docs/decisions.md, "M5 layer 2").

Reads: problem, student_steps, focus_step, error_type
Writes: misconception_candidates, misconception
Eval metric: Recall@k; MAP@k
"""

from typing import Any

from tutor.state import TutorState
from tutor.tools import retrieval

TOP_K = 5
MIN_SCORE = 0.85  # below this the best match is not trusted (dev: 91% answered, 96% of them right)


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
        "misconception": candidates[0] if candidates and candidates[0].score >= MIN_SCORE else None,
    }
