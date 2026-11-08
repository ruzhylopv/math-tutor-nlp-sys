"""Find the first wrong step, the step to talk about, and the error type.

Rules on the verdicts `verify` already computed; no model is called (see
docs/plans/nodes/2026-10-27-m4a-localize.md). The steps are scanned once, in order, and the
first step with a problem decides (a `reason` or `other` line SymPy could not read was never
compared, so it is skipped and is never the focus):
- `not_valid`: that step, `algebraic_transformation`.
- `unparsable`: an `equation` line SymPy could not judge, so there is no first error step, but
  that step is the focus; `other`.
- a valid step whose justification claim is false: that step, `reasoning_result_mismatch`.
If every step is fine but the final answer is wrong: a non-reversible (`implies`) step means
roots may have been added and never rejected (`omission_extraneous_root`, the first such step is
the focus); otherwise the student stopped before an answer (`incomplete`, the last valid line that
is not a check line is the focus). With no such line it is `other`, with no focus. With nothing
wrong all three fields are None.

A failed check line (`check_holds` False) is information, not an error: it is how a student
rejects an extraneous root. Only the first error is reported.

Known limits:
- After an unparsable step, later errors are not reported: the first problem wins.
- A wrong arithmetic claim written as a check line is not flagged (`check_holds` is ignored).
- The omission rule can fire when the student ran a check line but the answer is wrong for
  another reason.

Reads: step_verdicts, is_correct, student_steps
Writes: first_error_step, focus_step, error_type
Eval metric: first-error-step accuracy; error-type accuracy; mismatch detection rate
"""

from typing import Any

from tutor.state import ErrorType, StepVerdict, TutorState
from tutor.tools.diagnosis import VALID_RELATIONS, is_skipped_line


def _outcome(first: int | None, focus: int | None, error_type: ErrorType | None) -> dict[str, Any]:
    return {"first_error_step": first, "focus_step": focus, "error_type": error_type}


def _step_problem(verdict: StepVerdict) -> dict[str, Any] | None:
    """What is wrong with this step on its own, or None."""
    index = verdict.step_index
    if verdict.relation == "not_valid":
        return _outcome(index, index, "algebraic_transformation")
    if verdict.relation == "unparsable":
        return _outcome(None, index, "other")
    if verdict.justification_claims_ok is False:
        return _outcome(index, index, "reasoning_result_mismatch")
    return None


def localize(state: TutorState) -> dict[str, Any]:
    """Apply the rules in the module docstring to the verdicts."""
    steps = state.get("student_steps", [])
    verdicts = [v for v in state.get("step_verdicts", []) if not is_skipped_line(v, steps)]
    for verdict in verdicts:
        problem = _step_problem(verdict)
        if problem is not None:
            return problem
    if state.get("is_correct", False):
        return _outcome(None, None, None)
    for verdict in verdicts:
        if verdict.relation == "implies":
            return _outcome(None, verdict.step_index, "omission_extraneous_root")
    valid = [
        v.step_index for v in verdicts if v.relation in VALID_RELATIONS and v.check_holds is None
    ]
    if valid:
        return _outcome(None, valid[-1], "incomplete")
    return _outcome(None, None, "other")
