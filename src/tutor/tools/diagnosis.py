"""Pure helpers shared by the diagnosis nodes and the graph."""

from tutor.state import TutorState

VALID_RELATIONS = ("equivalent", "implies")


def is_clean_solution(state: TutorState) -> bool:
    """True when the final answer is correct, every step is valid and no justification is flagged.

    A step is valid when it is equivalent to, or implied by, the previous one. Unparsable and
    not_valid steps are not valid. How substitute / check steps are judged is settled in M2.
    """
    if not state.get("is_correct", False):
        return False
    for verdict in state.get("step_verdicts", []):
        if verdict.relation not in VALID_RELATIONS or verdict.justification_claims_ok is False:
            return False
    return True
