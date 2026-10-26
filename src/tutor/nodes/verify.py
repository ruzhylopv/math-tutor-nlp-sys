"""Check the final answer and each step with SymPy.

Step relations: equivalent / implies / narrows / not_valid / unparsable. Step 1 is compared with
the problem statement, so `problem` must be a plain-text statement (parse_input's job, M3); if it
does not parse, step 1 is `unparsable` and nothing is compared. A line that is a closed statement
(a check such as `sqrt(9+7) = 9-5`) is judged on its own truth and is not the predecessor of the
next step. `justification_claim`s are judged when they are closed statements.

Reads: problem, student_steps
Writes: is_correct, step_verdicts
Eval metric: answer-check accuracy; step-verdict accuracy
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
        if not parses(previous):
            notes = "the previous line or problem statement does not parse; nothing was compared"
            relation = "unparsable"
        else:
            relation = step_relation(previous, step.claim, original)
        closed = is_closed_statement(step.claim)
        if closed:
            notes = (notes + " check line").strip()
        elif parses(step.claim):
            previous = step.claim
        claim_ok = claim_truth(step.justification_claim) if step.justification_claim else None
        verdicts.append(
            StepVerdict(
                step_index=index,
                relation=relation,
                justification_claims_ok=claim_ok,
                notes=notes,
            )
        )
    answer_lines = [step.claim for step in steps if not is_closed_statement(step.claim)]
    final_line = answer_lines[-1] if answer_lines else ""
    return {
        "is_correct": bool(final_line) and final_answer_matches(problem, final_line) is True,
        "step_verdicts": verdicts,
    }
