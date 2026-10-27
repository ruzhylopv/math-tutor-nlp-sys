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
| `kind` | `generated_not_valid`, or the hand-written kind (`not_valid`, `lost_solution`, `omission`, `mismatch`, `mismatch_then_invalid`, `correct_answer_invalid_step`, `several_errors`, `unparsable`, `incomplete`, `control`, `checker_limit`) |
| `source` | `generated` or `handwritten` |

The eval runs the real `verify` and then `localize` on each case. There is no model.

Where the labels come from:
- `generated`: a step chain mined from a MATH solution (Algebra, Prealgebra, Intermediate Algebra, levels 1-3; one chain
  per problem), with one step made wrong by `corrupt.py`. The first wrong step is known by construction, and the type is
  `algebraic_transformation`. A chain is kept only if `verify` accepts every uncorrupted step and, after the corruption,
  its first problem is a `not_valid` verdict at exactly that step. So the selection uses the code under test.
- `handwritten`: 35 cases written by the agent (dev 18, test 17), with the expected values worked out by reading each
  attempt, then compared with the pipeline (a test fails on any disagreement). That agreement is not a fully blind
  check: about ten cases were probed with `verify` before their labels were finalized, and one label was revised after
  probing. The lost-solution cases (`x^2 = 3x` answered with `x = 3`) were `other` in the approved plan and were
  relabelled `algebraic_transformation` after probing showed `verify` calls the step `not_valid`. That label is a design
  choice (a step that is not a valid consequence of the previous one), not independent ground truth. The cases added
  after the review (3 `mismatch` and a second case of each singleton kind) were labelled by reading before anything was
  run, and all agreed with the pipeline. The `checker_limit` case (`2x + 1 > 7`, a correct solution) is not worked out by
  reading: it records a limitation of the checker (no inequalities), so `other` is what the checker can say, not a claim
  about the student. The cases are grouped by problem text and each whole group goes to one split (a deterministic greedy
  rule that keeps both splits covering every error type and as many kinds as possible), so no problem is in both splits.
  Kinds that sit on one problem only (`lost_solution`, `checker_limit`) are in dev only. The developer spot-checks a
  sample (`provenance.spot_check` is `pending`).

**Headline numbers:** report `case_accuracy/source=handwritten` and `case_accuracy/source=generated` separately. Do not
quote the blended `case_accuracy` alone. In the real build only about 4 of 60 dev and 2 of 60 test generated problems are
equations; the rest are arithmetic or expression simplification (for example `sqrt(25 + 144)`), so the blended number is
dominated by a near-trivial group.

How much to trust a metric: accuracy on the generated cases is high by construction (a regression suite). The
hand-written cases are the discriminating ones, and there are few of them per type (a handful in each split). Known limits:
- Inequalities and other out-of-grammar steps are `unparsable` by design of the checker, so `other` there is the
  expected label, not a claim that the student erred.
- Only the first error is reported; several errors in one attempt are one case with the first one labelled.
- The generated errors are single-token edits, easier than student errors.
- A failed check line is information, not an error (see the `localize` docstring).

## retrieve.jsonl (M4b)
One line per query: the state `retrieve` reads at the moment of a wrong step. Built by
`uv run python -m evals.builders.build_retrieve` (no outside data). The catalogue it searches is
`src/tutor/data/misconceptions.json` (119 hand-written entries).

| Field | Meaning |
|---|---|
| `id` | `gen/<entry>#<n>`, `wrap/<entry>#<n>` or `hand/<nnn>` |
| `problem`, `steps`, `focus_step`, `error_type`, `topic` | the state: `problem` is the line before the focus step for a generated query |
| `expected` | the catalogue entry id that the wrong step shows |
| `category` | the entry's category |
| `source` | `generated`, `generated_wrapped` or `handwritten` |

Where the labels come from:
- `generated`: 99 mechanical wrong rules (`evals/builders/misconception_rules.py`), four draws each. A rule turns a
  correct line into the line a student with that misconception would write, with random numbers and variable
  letters; SymPy confirmed each wrong line is really wrong. So the true misconception is known by construction.
  **These are near-copies of the catalogue examples**: `retrieve` compares shapes (numbers and variables abstracted),
  and for 89 of the 99 rules the query's shape equals the example's. The same author wrote both, so a high score here
  is close to a lookup and says little.
- `generated_wrapped`: the same rules with both lines inside the same larger expression (a term added to both sides of
  an equation, or a term added to or a factor multiplying an expression), two draws per rule, so the shape is no
  longer the example's. This is the first, mild perturbation; rules whose lines contain `or` or `+-` are not
  wrapped. The wrapped number is the more honest one for generated queries.
- `handwritten`: 38 queries (20 dev, 18 test), worked out by reading, for the entries without a rule (inequalities,
  translations, ...) and some paraphrases of mechanical ones. The developer spot-checks a sample (`spot_check:
  pending`).
- `M064`, `M067` and `M068` have no query: they are about a root accepted without a check or rejected for a wrong
  reason, which no single step's shape shows (`UNREACHABLE` in `handwritten_queries.py`).
- Entries alternate between dev and test by id (M001 dev, M002 test, ...), each with its queries, so no entry is in
  both splits and both cover every category. Sibling entries (`M037`/`M038`, `M078`/`M079`, ...) fall on opposite
  sides, so tuning on dev transfers to test more than it would for a split by family.

How much to trust a metric:
- Quote per-source numbers, mainly `generated_wrapped` and `handwritten`. The hand-written set is small (20 in dev; one
  query is 5 points).
- Recall@k is optimistic: one author wrote the catalogue and the queries, and nothing here is real student work.
- Entries about inequalities and a bare plus-or-minus cannot be reached in the full pipeline: `verify` cannot parse
  those steps, so `localize` gives `other` and `retrieve` returns nothing. Here `retrieve` is evaluated on its own.
- The test split is no longer untouched. Its aggregate scores were printed once while the builder was previewed,
  before tuning, and a reviewer later ran `retrieve` over it and looked at the misses to diagnose labels. No example
  was used to tune anything, but the test number should be reported with this caveat (`docs/decisions.md`).

## hint.jsonl (M5)
Built from `retrieve.jsonl` by `uv run python -m evals.builders.build_hint [--splits dev test]`; no new labels. Each line
is a retrieve query (`id`, `problem`, `steps`, `focus_step`, `error_type`, `topic`, `expected` = the catalogue entry the
wrong step shows, `category`, `source`, `provenance`) plus `level`, the hint level 1-4 to write. All hand-written
queries are kept; the rest (up to 60 cases in all) are generated queries taken in turn over categories, alternating
`generated_wrapped` and `generated`. Levels are dealt in turn, so each has a quarter of the cases. The eval gives
`hint` the gold misconception, so it measures the hint and not `retrieve`. The wrong steps are single-rule rewrites,
easier than real student work. `test/hint.jsonl` is protected: the developer runs the builder for it.
