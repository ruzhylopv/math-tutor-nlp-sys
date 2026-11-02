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

A definition (`t = x + 1`: a new letter set to an expression in known letters, see
`algebra.definition_of`) is recognised by its form, not by the step's `kind`. Its relation is
`equivalent` with the note "definition", it is not the predecessor of the next line, and later
lines are compared with the defined letters replaced. A line labelled `reason` or `other` that
SymPy cannot read is `unparsable` with a note and is not the predecessor; one that parses is
checked like any line, so a wrong equation is never hidden by its label. The final answer is the
last line that is not a check, a definition or such a reason line, and it must not use a defined
letter (`t = 5` is not an answer to an equation in x).

Reads: problem, student_steps
Writes: is_correct, step_verdicts
Eval metric: step-verdict accuracy (answer-check accuracy waits for the answer dataset)
"""

from typing import Any

from tutor.state import Relation, StepVerdict, TutorState
from tutor.tools.algebra import (
    claim_truth,
    definition_of,
    final_answer_matches,
    is_closed_statement,
    is_equation,
    letters,
    parses,
    step_relation,
)

REASON_NOTE = "reason line, not compared"


def verify(state: TutorState) -> dict[str, Any]:
    """Judge every step against the previous one and the final answer against the problem."""
    steps = state.get("student_steps", [])
    problem = state.get("problem", "")
    original = problem if is_equation(problem) else None
    previous = problem
    definitions: dict[str, str] = {}
    final_line = ""
    verdicts: list[StepVerdict] = []
    for index, step in enumerate(steps, start=1):
        notes = ""
        relation: Relation
        check_holds: bool | None = None
        definition = definition_of(step.claim, problem, definitions)
        if is_closed_statement(step.claim):
            relation = "equivalent"
            check_holds = claim_truth(step.claim)
            notes = "check line"
        elif definition is not None:
            definitions[definition[0]] = definition[1]
            relation = "equivalent"
            notes = "definition"
        elif step.kind in ("reason", "other") and not parses(step.claim):
            relation = "unparsable"
            notes = REASON_NOTE
        elif not parses(previous):
            notes = "the previous line or problem statement does not parse; nothing was compared"
            relation = "unparsable"
            final_line = step.claim
            if parses(step.claim):
                previous = step.claim
        else:
            relation = step_relation(previous, step.claim, original, definitions)
            final_line = step.claim
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
    answers = bool(final_line) and not letters(final_line) & definitions.keys()
    return {
        "is_correct": answers and final_answer_matches(problem, final_line) is True,
        "step_verdicts": verdicts,
    }
