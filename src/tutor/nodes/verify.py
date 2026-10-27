"""Check the final answer and each step with SymPy.

Step relations: equivalent / implies / narrows / not_valid / unparsable. Step 1 is compared with
the problem statement, so `problem` must be a plain-text statement (parse_input's job, M3); if it
does not parse, step 1 is `unparsable` and nothing is compared.

A line that is a closed statement is a check (`sqrt(9+7) = 9-5`). Its relation is `equivalent`
(it is not a derivation step), its truth goes to `check_holds`, and it is not the predecessor of
the next line. A check that fails is information, not an error: it is how a student rejects an
extraneous root. Consequence: a wrong arithmetic claim written as a check line is not flagged by
`verify`, and `localize` deliberately ignores `check_holds`, so it is not flagged there either (a
known, documented limit; see docs/plans/nodes/2026-10-27-m4a-localize.md).
`justification_claim`s are judged when they are closed statements.

Reads: problem, student_steps
Writes: is_correct, step_verdicts
Eval metric: step-verdict accuracy (answer-check accuracy waits for the answer dataset)
"""

from typing import Any

from tutor.state import Relation, StepVerdict, TutorState
from tutor.tools.algebra import (
    claim_truth,
    final_answer_matches,
    is_closed_statement,
    is_equation,
    parses,
    step_relation,
)


def verify(state: TutorState) -> dict[str, Any]:
    """Judge every step against the previous one and the final answer against the problem."""
    steps = state.get("student_steps", [])
    problem = state.get("problem", "")
    original = problem if is_equation(problem) else None
    previous = problem
    verdicts: list[StepVerdict] = []
    for index, step in enumerate(steps, start=1):
        notes = ""
        relation: Relation
        check_holds: bool | None = None
        if is_closed_statement(step.claim):
            relation = "equivalent"
            check_holds = claim_truth(step.claim)
            notes = "check line"
        elif not parses(previous):
            notes = "the previous line or problem statement does not parse; nothing was compared"
            relation = "unparsable"
            if parses(step.claim):
                previous = step.claim
        else:
            relation = step_relation(previous, step.claim, original)
            if parses(step.claim):
                previous = step.claim
        claim_ok = claim_truth(step.justification_claim) if step.justification_claim else None
        verdicts.append(
            StepVerdict(
                step_index=index,
                relation=relation,
                justification_claims_ok=claim_ok,
                check_holds=check_holds,
                notes=notes,
            )
        )
    answer_lines = [step.claim for step in steps if not is_closed_statement(step.claim)]
    final_line = answer_lines[-1] if answer_lines else ""
    return {
        "is_correct": bool(final_line) and final_answer_matches(problem, final_line) is True,
        "step_verdicts": verdicts,
    }
