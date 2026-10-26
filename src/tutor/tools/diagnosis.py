"""Pure helpers shared by the diagnosis nodes and the graph."""

from tutor.state import TutorState

VALID_RELATIONS = ("equivalent", "implies", "narrows")


def is_clean_solution(state: TutorState) -> bool:
    """True when the final answer is correct, every step is valid and no justification is flagged.

    A step is valid when it is equivalent to, or implied by, the previous one, or when it narrows
    the solution set to the original problem's own solution set (rejecting an extraneous root).
    Unparsable and not_valid steps are not valid, so they send the run on to `localize`, which
    has no dedicated error type for unparsable steps yet (taxonomy decision, M4). With no steps
    at all the answer alone decides; `parse_input` routes a final answer without working to
    `ask` before this runs.
    """
    if not state.get("is_correct", False):
        return False
    for verdict in state.get("step_verdicts", []):
        if verdict.relation not in VALID_RELATIONS or verdict.justification_claims_ok is False:
            return False
    return True
