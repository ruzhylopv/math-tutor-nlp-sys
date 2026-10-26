# Datasets

Fixed `dev/` and `test/` splits per component. Iterate on dev only; test is for the final reported
numbers. Never edit a dataset or its labels to make a result pass.

## verify_steps.jsonl (M2)
One line per pair of consecutive lines of a solution. Built by
`uv run python -m evals.builders.build_verify --math-dir <dir with train.jsonl and test.jsonl>`
(the `math_splits` of PRM800K, MATH as JSONL; raw files stay outside the repo).

| Field | Meaning |
|---|---|
| `id` | `math/<unique_id>#<n>`, `gen/<...>` (generated negative) or `hand/<nnn>` |
| `task_type` | solve, simplify, expand or factor (a rough tag from the problem text) |
| `problem` | the problem as written in MATH or by hand (LaTeX) |
| `prev`, `curr` | two consecutive lines in plain text, as `tutor.tools.algebra` parses them |
| `relation` | `equivalent`, `implies`, `narrows`, `not_valid` or `unparsable` |
| `original` | the problem's own equation, only where `narrows` or a lost solution needs it |
| `source` | `math`, `generated` or `handwritten` |
| `provenance` | where it came from; generated cases record the corruption rule and the seed |

Where the labels come from:
- `math`: `equivalent`, from the human author of the MATH solution. Kept only if SymPy agrees; the
  rest goes to `review/verify_steps_disagreements.jsonl` (author typos, lines that hold only under a
  condition) and is not part of any split.
- `generated`: `not_valid`, from the rule that broke a mined line. Kept only when exact arithmetic
  finds a witness point, so a corruption that is secretly still equivalent is discarded.
- `handwritten`: written by the agent with the relation worked out by hand, then cross-checked against
  the checker. The developer spot-checks a sample (`provenance.spot_check` is `pending`).

Splits: mined and generated cases by source problem with a fixed seed (no problem in both splits);
hand-written cases stratified by relation, because they share problem texts.

Known limits:
- The rare relations are few in test (implies 4, narrows 2, unparsable 5): report them with their
  counts and do not over-read a single wrong case.
- Mined pairs keep only identity lines (same variables on both sides); conditions, substitutions,
  complex numbers, function notation and custom operations are filtered out.
- One variable per equation, real solutions only, no inequalities (see the M2 plan).
