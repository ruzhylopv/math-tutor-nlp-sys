# Plan: verify substitutes definitions and skips reason lines (approved 2026-11-02)

Layer 3 of `docs/plans/design/2026-11-02-flexible-input.md`. The developer considered a general
"compare what parses, skip the rest" rewrite (dropping `Step.kind`) and chose this plan as written.

## Changes
- **Tools** (`src/tutor/tools/algebra.py`):
  - `definition_of(line, problem, known)`: `(name, rhs)` when the line is `letter = expression`, the
    letter is not in the problem and not already defined, the right side parses and uses a problem
    variable or an earlier definition; else None.
  - `step_relation(prev, curr, original, definitions=None)`: after parsing, defined letters are
    replaced on both sides (in order, so a definition may use an earlier one); then the comparison
    runs as today.
- **Node** (`src/tutor/nodes/verify.py`):
  - A definition line: `equivalent`, note "definition", recorded, not the predecessor.
  - A `reason` / `other` line SymPy cannot read: `unparsable`, note "reason line, not compared", not
    the predecessor. One that parses is checked like any line (SymPy decides, not the label).
  - Final answer: the last line that is not a check, a definition or a reason/other line, not
    substituted (an answer still in the new letter is not an answer).
  - Check lines and the "previous line does not parse" rule unchanged.
- **Decision**: definitions are recognised by form, not by `kind` (kind accuracy is not measured yet,
  and a mislabelled definition would bring back the step-1 bug).

## Eval
- `evals/builders/verify_chains.py` writes `evals/datasets/dev/verify_chains.jsonl`: 12-15
  hand-written chains (problem, steps with claim and kind, expected relation per step, expected
  `is_correct`), dev only, `spot_check: pending`.
- `eval_verify.py` adds `chain/step_accuracy`, `chain/recall/<relation>`, `chain/is_correct_accuracy`;
  the pair metrics stay as they are. Deterministic, no model calls.

## Tests and docs
Algebra tests for `definition_of` and substitution; node tests for definition chains, reason lines
and the final answer; eval tests for the chain metrics. Architecture verify row, CRISP-DM entry,
decisions entry.

## PR
A two-layer stack: (1) algebra, node and tests; (2) chain dataset, eval, docs.
