"""Pure helpers shared by the diagnosis nodes and the graph."""

from collections.abc import Sequence

from tutor.state import Step, StepVerdict, TutorState

VALID_RELATIONS = ("equivalent", "implies", "narrows")


def is_skipped_line(verdict: StepVerdict, steps: Sequence[Step]) -> bool:
    """True for a `reason` or `other` line SymPy could not read: it was never compared.

    A line with a false arithmetic claim is not skipped: the claim itself is wrong.
    """
    if verdict.relation != "unparsable" or verdict.justification_claims_ok is False:
        return False
    if not 1 <= verdict.step_index <= len(steps):
        return False
    return steps[verdict.step_index - 1].kind in ("reason", "other")


def compared_line(state: TutorState, focus: int) -> str:
    """The line step `focus` was really compared with, or the problem when no line came before it.

    `verify` does not use a skipped line, a check line or a definition as the predecessor. A step
    with no verdict counts as a normal predecessor.
    """
    steps = state.get("student_steps", [])
    verdicts = {verdict.step_index: verdict for verdict in state.get("step_verdicts", [])}
    for index in range(focus - 1, 0, -1):
        verdict = verdicts.get(index)
        if verdict is None or not (
            is_skipped_line(verdict, steps)
            or verdict.check_holds is not None
            or verdict.notes == "definition"
        ):
            return steps[index - 1].claim
    return state.get("problem", "")


def is_clean_solution(state: TutorState) -> bool:
    """True when the final answer is correct, every step is valid and no justification is flagged.

    A step is valid when it is equivalent to, or implied by, the previous one, or when it narrows
    the solution set to the original problem's own solution set (rejecting an extraneous root).
    Unparsable and not_valid steps are not valid, so they send the run on to `localize`, which
    gives unparsable steps the error type `other`. A `reason` or `other` line SymPy could not read
    is skipped: it was never compared, so it says nothing about the solution. With no steps
    at all the answer alone decides; `parse_input` routes a final answer without working to
    `ask` before this runs.
    """
    if not state.get("is_correct", False):
        return False
    steps = state.get("student_steps", [])
    for verdict in state.get("step_verdicts", []):
        if is_skipped_line(verdict, steps):
            continue
        if verdict.relation not in VALID_RELATIONS or verdict.justification_claims_ok is False:
            return False
    return True
