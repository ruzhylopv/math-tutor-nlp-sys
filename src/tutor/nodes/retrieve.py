"""Search the misconception catalogue for the misconception behind the wrong step.

The query is plain text in the shape of the catalogue's examples: the topic, the error type, and the
line before the focus step and the line the student wrote there ("previous -> written"). The top 5
matches go to `misconception_candidates` and the best one to `misconception`. With nothing to look
for (no focus step, or an error type of None or `other`) both are empty. No score threshold yet
(docs/plans/nodes/2026-10-27-m4b-retrieve.md).

Reads: problem, student_steps, focus_step, topic, error_type
Writes: misconception_candidates, misconception
Eval metric: Recall@k; MAP@k
"""

from typing import Any

from tutor.state import TutorState
from tutor.tools import retrieval

TOP_K = 5


def build_query(state: TutorState) -> str | None:
    """The query text, or None when there is nothing to look for."""
    focus = state.get("focus_step")
    error_type = state.get("error_type")
    steps = state.get("student_steps", [])
    if error_type in (None, "other") or focus is None or not 1 <= focus <= len(steps):
        return None
    previous = state.get("problem", "") if focus == 1 else steps[focus - 2].claim
    parts = [state.get("topic", ""), error_type.replace("_", " ")]
    return (
        ". ".join(part for part in parts if part)
        + f". Example: {previous} -> {steps[focus - 1].claim}"
    )


def retrieve(state: TutorState) -> dict[str, Any]:
    """Look the focus step up in the catalogue."""
    query = build_query(state)
    candidates = retrieval.search(query, TOP_K) if query else []
    return {
        "misconception_candidates": candidates,
        "misconception": candidates[0] if candidates else None,
    }
