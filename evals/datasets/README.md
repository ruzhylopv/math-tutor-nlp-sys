# Datasets

Fixed `dev/` and `test/` splits per component. Iterate on dev only; test is for the final reported
numbers. Never edit a dataset or its labels to make a result pass.

**Status:** the files in `dev/` and `test/` were built before the M2 review fixes and are intentionally not
rebuilt (developer decision, 2026-10-26). The builder in `evals/builders/` is stricter than the build that produced
them (a preview gives dev 1,237 and test 479 cases against the committed 1,621 and 671), so it does not reproduce the
committed files, and about a dozen identical trivial pairs appear in both splits. Counts, rates and versions of the
committed build live in `review/verify_build_report.json`.

## verify_steps.jsonl (M2)
One line per pair of consecutive lines of a solution. Built by
`uv run python -m evals.builders.build_verify --math-dir <dir with train.jsonl and test.jsonl>`
from the `math_splits` of PRM800K (MATH as JSONL; raw files stay outside the repo, so the build cannot
be reproduced from the repo alone). It reads Algebra levels 1-3 only.

| Field | Meaning |
|---|---|
| `id` | `math/<unique_id>#<n>`, `gen/<...>` (generated negative) or `hand/<nnn>` |
| `task_type` | solve, simplify, expand, factor or other (a rough tag from the problem text) |
| `problem` | the problem as written in MATH or by hand (LaTeX) |
| `prev`, `curr` | two consecutive lines in plain text, as `tutor.tools.algebra` parses them |
| `relation` | `equivalent`, `implies`, `narrows`, `not_valid` or `unparsable` |
| `original` | the problem's own equation, only where `narrows` or a lost solution needs it |
| `source` | `math`, `generated` or `handwritten` |
| `provenance` | where it came from; generated cases record the corruption rule and the seed |

`unparsable` means "outside the checker's supported grammar", not "not mathematics": `sin(x) = 0`,
`x^2 > 4` and `5 / 0` are labelled `unparsable` because the checker handles one variable, real
solutions, no inequalities and no trigonometry.

### Where the labels come from
- `math`: `equivalent`, from the human author of the MATH solution, **kept only if SymPy agrees**.
  Pairs SymPy calls not equivalent are written to `review/verify_steps_disagreements.jsonl`, and pairs
  it cannot parse to `review/verify_steps_unparsable.jsonl`; neither is part of a split.
- `generated`: `not_valid`, from the rule that broke a mined line. Kept only when exact arithmetic
  finds a witness point, so a corruption that is secretly still equivalent is discarded. The edits are
  single-token (sign, number, exponent, a dropped term), not student-like errors.
- `handwritten`: written by the agent with the relation worked out by hand, then cross-checked against
  the checker. A label was changed during that cross-check (see `docs/decisions.md`), so accuracy on
  these is an agreement figure, not held-out performance. The developer spot-checks a sample
  (`provenance.spot_check` is `pending`). Several are near-duplicates of each other by design (the same
  template with other numbers), and some share a problem text across dev and test.

### Splits
Mined and generated cases are split by source problem with a fixed seed, so no problem is in both
splits; identical `(prev, curr, relation)` pairs from different problems are kept once. Hand-written
cases are split stratified by relation (every third case of each relation goes to test).

### How much to trust a metric on these splits
Accuracy here is high by construction, so treat the splits as a regression suite:
- mined positives are exactly the pairs the checker accepts, so recall on them is about 100% and a
  parser false negative can never show up;
- generated negatives are easy single edits; the hand-written cases are the discriminating ones;
- most mined cases are trivial arithmetic (`3^2 -> 9`), and equation pairs are few, so the solution-set
  path is covered mostly by hand-written cases;
- rare relations (`implies`, `narrows`, `unparsable`) have only a handful of cases per split: report them
  with their counts.

The independent numbers are in `review/verify_build_report.json`: how often the checker agrees with a
human-written step (agreement rate on parseable pairs) and how often it cannot parse one.

### Review files
- `review/verify_spotcheck_generated.jsonl`: a seeded 20% sample of the generated negatives, for the
  developer to read. The hand-written cases carry `spot_check: pending` in their provenance.

### Known limits
- Algebra levels 1-3 only; identity lines only (same variables on both sides, no complex numbers,
  function notation, custom operations or conditions); one variable per equation, real solutions only.
- Two unrelated equations that share a solution (`x + 3 = 5`, `x + 7 = 9`) could still be mined as a pair.
- The datasets are frozen once approved. Do not rebuild after a checker change without saying so:
  membership depends on the code under test.
