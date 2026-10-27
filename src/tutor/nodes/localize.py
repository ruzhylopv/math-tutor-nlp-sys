"""Find the first wrong step, the step to talk about, and the error type.

Rules on the verdicts `verify` already computed; no model is called (see
docs/plans/nodes/2026-10-27-m4a-localize.md). The steps are scanned once, in order, and the
first step with a problem decides:
- `not_valid`: that step, `algebraic_transformation`.
- `unparsable`: SymPy could not judge it, so there is no first error step, but that step is the
  focus; `other`.
- a valid step whose justification claim is false: that step, `reasoning_result_mismatch`.
If every step is fine but the final answer is wrong: a non-reversible (`implies`) step means
roots may have been added and never rejected (`omission_extraneous_root`, the first such step is
the focus); otherwise `other` (for example a lost solution through a `narrows` step). With
nothing wrong all three fields are None.

A failed check line (`check_holds` False) is information, not an error: it is how a student
rejects an extraneous root. Only the first error is reported.

Known limits:
- After an unparsable step, later errors are not reported: the first problem wins.
- A wrong arithmetic claim written as a check line is not flagged (`check_holds` is ignored).
- The omission rule can fire when the student ran a check line but the answer is wrong for
  another reason.

Reads: step_verdicts, is_correct
Writes: first_error_step, focus_step, error_type
Eval metric: first-error-step accuracy; error-type accuracy; mismatch detection rate
"""

from typing import Any

from tutor.state import ErrorType, StepVerdict, TutorState


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
    verdicts = state.get("step_verdicts", [])
    for verdict in verdicts:
        problem = _step_problem(verdict)
        if problem is not None:
            return problem
    if state.get("is_correct", False):
        return _outcome(None, None, None)
    for verdict in verdicts:
        if verdict.relation == "implies":
            return _outcome(None, verdict.step_index, "omission_extraneous_root")
    return _outcome(None, None, "other")
