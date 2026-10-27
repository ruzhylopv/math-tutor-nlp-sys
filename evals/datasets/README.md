# Datasets

Fixed `dev/` and `test/` splits per component. Iterate on dev only; test is for the final reported
numbers. Never edit a dataset or its labels to make a result pass.

**Status:** the files in `dev/` and `test/` were built before the M2 review fixes and are intentionally not
rebuilt (developer decision, 2026-10-26). The builder in `evals/builders/` is stricter than the build that produced
them (a preview gives dev 1,237 and test 479 cases against the committed 1,621 and 671), so it does not reproduce the
committed files. Dev and test share 12 identical (prev, curr, relation) pairs; most are trivial, but some are not
(for example `(x + y)^2 -> x^2 + y^2 + 2xy` and `xy-2x-yx+2y -> -2x+2y`). This is dev/test leakage, and the reported test
numbers inherit it. Counts, rates and versions of the
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

## classify.jsonl (M3)
One line per MATH problem: `id`, `problem` (LaTeX as in MATH), `subject`, `level` (1-5). Built by
`uv run python -m evals.builders.build_classify --math-dir <dir with train.jsonl and test.jsonl>`. Labels are MATH's own,
human-assigned, so they do not depend on our code. 60 problems per subject per split (420 each), problems ordered by a
seeded hash, first 60 to dev and next 60 to test, identical texts kept once. Counts: `review/classify_build_report.json`.
Limits: the eval feeds LaTeX; in use `classify` receives `parse_input`'s plain-text problem. Level labels are noisy at the
edges, so the eval also reports "within one level".

## parse_input.jsonl (M3)
One line per student message. Built by
`uv run python -m evals.builders.build_parse_input --math-dir <dir with train.jsonl and test.jsonl>`.

| Field | Meaning |
|---|---|
| `id` | `math/<unique_id>` (generated) or `hand/<nnn>` |
| `message` | the student's raw message |
| `stored_problem` | the problem already in the session, or null |
| `expected_problem` | the new problem the message states, or null (the stored one stays) |
| `expected_steps` | the claims, in order, as plain-text math (a wrong step stays wrong) |
| `features` | generated messages: the kind (`full`, `steps_only`, `problem_only`, `answer_only`, `question_only`), the layout, the notation, and `chatty`, `typos`, `wrong_step`. Hand-written messages use free-form descriptive tags (in use: `answer_only`, `chatty`, `connectors`, `greeting`, `justifications`, `latex`, `new_problem`, `numbered`, `one_line`, `problem_only`, `question_only`, `smalltalk`, `spoken`, `steps_only`, `typos`, `unicode`, `word_problem`, `wrong_step`) |
| `source` | `generated` or `handwritten` |

The labels come from the rendering direction: a step chain is mined from a MATH solution (Algebra, Prealgebra,
Intermediate Algebra, levels 1-3; one chain per problem; first line = problem, the rest = steps), one step is sometimes
made wrong by `corrupt.py`, and the chain is written as a message (`render_message.py`). 150 generated messages per split,
split by problem hash; 20 (dev) and 9 (test) hand-written ones. `review/parse_input_spotcheck.jsonl` is a seeded sample of
24 generated messages from the dev split only (the test split stays unread while the prompt is tuned); hand-written cases carry `spot_check: pending`.

How much to trust a metric: the messages are synthetic and only as messy as the renderer makes them (no real student
text), most chains are arithmetic or expressions (about a sixth of the generated messages are equations: 25 of 150 in dev, 27 of 150 in test), and spoken math is rare in generated
data because most chains contain brackets or fractions. Hand-written cases are the discriminating ones.

## localize.jsonl (M4a)
One line per attempt. Built by `uv run python -m evals.builders.build_localize --math-dir <dir with train.jsonl and test.jsonl>`.

| Field | Meaning |
|---|---|
| `id` | `math/<unique_id>#<step>` (generated) or `hand/<nnn>` |
| `problem` | plain-text math, as `parse_input` would produce |
| `steps` | the student's steps: `claim`, `justification`, `justification_claim` |
| `expected` | `first_error_step`, `focus_step` (1-based or null) and `error_type` (null when nothing is wrong) |
| `kind` | `generated_not_valid`, or the hand-written kind (`not_valid`, `lost_solution`, `omission`, `mismatch`, `unparsable`, `incomplete`, `control`, ...) |
| `source` | `generated` or `handwritten` |

The eval runs the real `verify` and then `localize` on each case. There is no model.

Where the labels come from:
- `generated`: a step chain mined from a MATH solution (Algebra, Prealgebra, Intermediate Algebra, levels 1-3; one chain
  per problem), with one step made wrong by `corrupt.py`. The first wrong step is known by construction, and the type is
  `algebraic_transformation`. A chain is kept only if `verify` accepts every uncorrupted step and, after the corruption,
  its first problem is a `not_valid` verdict at exactly that step. So the selection uses the code under test.
- `handwritten`: written by the agent, with the expected values worked out by reading each attempt, then compared with
  the pipeline (a test fails on any disagreement; none was found, but about ten cases were probed with `verify` before
  their labels were finalized, so the agreement is not a fully blind check). Within each kind the cases alternate between
  dev and test. The developer spot-checks a sample (`provenance.spot_check` is `pending`).

How much to trust a metric: accuracy on the generated cases is high by construction (a regression suite). The
hand-written cases are the discriminating ones, and there are few of them per type (a handful in each split). Known limits:
- Inequalities and other out-of-grammar steps are `unparsable` by design of the checker, so `other` there is the
  expected label, not a claim that the student erred.
- Only the first error is reported; several errors in one attempt are one case with the first one labelled.
- The generated errors are single-token edits, easier than student errors.
- A failed check line is information, not an error (see the `localize` docstring).

