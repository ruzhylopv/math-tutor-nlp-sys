# Plan: localize skips reason lines and reports `incomplete` (approved 2026-11-08)

Layer 4 of `docs/plans/design/2026-11-02-flexible-input.md`. Evals are debt for layers 4-6 (developer's
decision): no new cases and no eval run in this layer.

## Changes
- `src/tutor/nodes/localize.py`: a `reason` / `other` line SymPy cannot read is skipped and is never the
  focus; an `equation` line SymPy cannot read stays the focus. Every checked line valid, answer not
  correct and no `implies` step: `incomplete`, focus on the last valid line (never a check line). No
  valid line to focus on: `other`, no focus.
- `src/tutor/tools/diagnosis.py`: `is_clean_solution` skips the same lines, so a correct solution with a
  reason line is clean (not named in the design plan; needed so it is not hinted).
- `src/tutor/nodes/retrieve.py`: `incomplete` has nothing to look up. The learner DB then records nothing
  for it, because only retrieved misconceptions are recorded.

## Existing tests and labels (developer's decisions, 2026-11-08)
- `test_valid_steps_with_a_wrong_answer_and_no_implication_is_other` now expects `incomplete`, and the set of
  error types in `test_the_hand_written_cases_are_well_formed_and_cover_every_type` includes it.
- Relabelled to `incomplete` with the focus on the last valid line: the two "incomplete" cases in
  `evals/builders/handwritten_localize.py` and dev `hand/004`.
- Open debt: test `hand/010` (line 7 of `evals/datasets/test/localize.jsonl`) still says `other`, no focus. The
  test split is write-protected, so the developer changes it to `"focus_step": 2, "error_type": "incomplete"`.
