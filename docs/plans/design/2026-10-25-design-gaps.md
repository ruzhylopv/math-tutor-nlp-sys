# Plan: close the design gaps from the PR #11 review (approved 2026-10-25)

Docs only. Resolves the three P1s and the state mismatches that the review of PR #11 found in the design.

## Decisions (approved by the developer)
1. `verify` short-circuits only when the answer is correct, every step is valid and no justification is
   flagged; otherwise the flow continues through `localize` and `retrieve`.
2. `diagnosis` and `hint` always return to the orchestrator, which has three modes chosen by a `stage`
   field. After diagnosis it sets or escalates the hint level in plain code; after a hint it runs the
   leakage check (retry once, then a canned hint) in plain code.
3. Numbers in hints come from a SymPy tool, never from the LLM. The tool's design stays OPEN.
Provisional numbers (hint levels 1-4, practice at the third occurrence) were proposed and not objected to.

## Files
`docs/architecture.md`, `docs/plans/design/2026-10-25-tutor-state-outline.md`, `docs/decisions.md`,
`docs/plans/README.md`, this plan.
