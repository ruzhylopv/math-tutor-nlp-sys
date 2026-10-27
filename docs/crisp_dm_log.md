# CRISP-DM log

CRISP-DM is applied twice: once for the whole project, and as a small loop per node (explore data,
build, evaluate, iterate). Evaluation entries are appended by the `run-eval` skill under
**Evaluation**.

## Business understanding
- 2026-10-25 | project | Students repeat the same algebra mistakes. Modern chatbots (ChatGPT etc.)
  can tutor well given enough context, and a prompt can ask for a Socratic structure, but that
  structure erodes over a long conversation, and a student who loses discipline can simply ask for
  the answer faster. The aim is a tutor that cannot be sped up: verification, the hint ladder and
  the leakage check are enforced by the system, not by the prompt. Success = correct diagnosis and
  helpful hints without answer leakage, also under pressure to skip steps. Scope and architecture:
  `docs/architecture.md`.

## Data understanding
- Planned, not started: explore MATH, GSM8K, ProcessBench / PRM800K and Eedi; note gaps that need
  hand-made sets (equivalence vs implication, reasoning-result mismatch, routing). Verify each
  source's format and licence first.
- 2026-10-25 | error taxonomy | Searched for published step-level error datasets: Cognitive Tutor /
  DataShop (24-label scheme), MathEDU, MR-GSM8K, ErrorRadar, MathCCS (links in
  `docs/architecture.md`). Nothing downloaded or verified. Next: check formats and licences, map their
  labels onto our four error types, count what does not fit. Open items: `docs/decisions.md`.
- 2026-10-26 | PRM800K and MATH | Inspected the small PRM800K files (phase2_test, phase1_test, math_splits/test) and the
  MATH dataset card; sizes, schema and the Algebra levels 1-3 yield are in `docs/plans/nodes/2026-10-26-m2-verify.md`.
  PRM800K is a good fit for the final-answer check and for localize (M4), a poor fit for step relations. The
  `phase2_train` file (435 MB) is not downloaded yet.
- 2026-10-26 | MATH labels for classify | MATH has 12,500 problems with human-assigned `subject` (Algebra 2,931; Prealgebra
  2,076; Intermediate Algebra 2,198; Geometry 1,350; Number Theory 1,409; Precalculus 1,291; Counting & Probability 1,245)
  and `level` 1-5, in the PRM800K `math_splits` files. `classify` uses them as labels; no finer topic taxonomy.
- 2026-10-26 | parse_input messages | No dataset of messy student algebra messages with a known parse was found or checked;
  the expected parse is instead known by construction: mined MATH step chains (one per problem; 535 were usable), rendered in
  four layouts and four notations, with typos in words only, chatty frames and some deliberately wrong steps, plus 29
  hand-written messages. Details and limits: `evals/datasets/README.md`. The prompt's "new or different problem" rule was written after reading hand-written case `hand/011`, which is in the test split; do not tune the prompt further on hand cases of the test split.
- 2026-10-25 | Eedi | A paper reports 1,857 questions; the number of distinct misconceptions and
  whether the scenario A/B misconceptions exist in it are unverified.

## Data preparation
- Planned, not started: convert each source to the per-component JSONL format; fixed dev/test splits.
- 2026-10-26 | verify_steps | Built `evals/datasets/{dev,test}/verify_steps.jsonl` from MATH Algebra levels 1-3 (mined
  identity pairs), rule-based corruptions with a witness guard, and 76 hand-written cases. Dev 1621, test 671, review 9.
  Format and limits: `evals/datasets/README.md`.
- 2026-10-26 | classify | Built the dev and test sets (420 problems each, 60 per MATH subject) from MATH's own labels.
- 2026-10-26 | parse_input | Wrote `evals/builders/build_parse_input.py`. Built by the developer's own run (the test split is protected): dev 170
  and test 159 messages (150 generated plus 20 and 9 hand-written), identical to a rebuild of the committed builder.

- 2026-10-27 | localize attempts | No public dataset has first-error labels for our `omission_extraneous_root` and
  `reasoning_result_mismatch` types (checked earlier, see `docs/architecture.md`), so the expected values come from
  construction (mined MATH chains with one corrupted step) and from 35 hand-written attempts (dev 18, test 17, split by
  problem group so no problem is in both). Built by the developer's own run (the test split is protected): dev 78 and test 77 attempts
  (60 generated plus 18 and 17 hand-written), identical to a rebuild of the committed builder. Caveats: (1) report `case_accuracy/source=handwritten` and `generated` separately and never
  the blended number alone, because in the real build only about 4 of 60 dev and 2 of 60 test generated problems are
  equations, the rest are arithmetic or expression simplification (e.g. `sqrt(25 + 144)`); (2) the lost-solution cases were
  `other` in the approved plan and were relabelled `algebraic_transformation` after probing `verify` showed `not_valid`,
  so that label is a design choice (a step that is not a valid consequence of the previous one), not independent ground
  truth; (3) the generated chains were selected with `verify`, so their accuracy is high by construction. Details and
  limits: `evals/datasets/README.md`.
- 2026-10-27 | retrieve catalogue and queries | The Eedi catalogue could not be downloaded, so the catalogue is hand-written (119
  school-algebra misconceptions in 13 categories, `src/tutor/data/misconceptions.json`) and the eval queries come from 99
  mechanical wrong rules (SymPy-confirmed), the same rules wrapped in a larger expression, and 38 hand-written queries.
  Dev 324 and test 300 queries (204 + 100 + 20 and 192 + 90 + 18). The plain generated queries are near-copies of the
  catalogue examples (89 of 99 rules); the wrapped and hand-written ones are the honest numbers. Three reasoning-level
  entries have no query. Details and limits: `evals/datasets/README.md`.

## Modeling
- Planned build order: verify, classify, localize, retrieve, hint, orchestrator + graph, checkpointer
  + scenarios, Streamlit UI.
- 2026-10-25 | M1 skeleton | State models, config, the OpenRouter client, the shared eval runner, eight stub
  nodes, the diagnosis subgraph and the main graph compile and pass 83 unit tests; `docs/graph.mmd` is the
  Mermaid export. No model has been called yet: `scripts/check_llm.py` is the next step to run by hand once
  `MODEL_NAME` is chosen. Plan: `docs/plans/design/2026-10-25-m1-skeleton.md`.
- 2026-10-26 | M3 input layer | `classify` (7 MATH subjects, levels 1-5, in-scope = Prealgebra, Algebra, Intermediate
  Algebra) and `parse_input` (problem and steps from the raw message, faithful transcription) implemented behind
  `tools/structured.call_structured` (one retry, eval cache); prompts have no dataset examples. Model for the evals:
  `nvidia/nemotron-3.5-super-vl:free`. No real-model run yet; unit tests mock the model. Plan:
  `docs/plans/nodes/2026-10-26-m3-input-layer.md`.

## Evaluation
<!-- Format: YYYY-MM-DD | <component> | <split> | <key metric>=<value> (change) | <git-hash> | note -->
- 2026-10-26 | verify | dev | accuracy=0.9975 (was 1.000; same committed dev data, fixed checker and node) | 6f3c644 | The 4
  cases that changed are `2^(3^2)`: stacked powers are rejected on purpose now (denial of service); the failed check
  line `hand/058` is mapped through `check_holds`. Still high by construction (see the next line). A preview rebuild
  with the stricter miner (decided not to rebuild, 2026-10-26; see docs/decisions.md) gives dev 1,237 and test 479 cases and an agreement of
  838 of 842 parseable pairs (99.5%) with a parse rate of 92%; no independent number exists for the generated and
  hand-written relations.
- 2026-10-26 | verify | dev | accuracy=1.000 (baseline; n=1621) | 631144b | High by construction, a regression suite
  and not independent evidence: mined positives were kept only where SymPy agreed with the MATH author, generated
  negatives passed a witness check, hand-written labels were reconciled with the checker. Independent numbers
  (`evals/datasets/review/verify_build_report.json`): the checker agrees with the author on 1118 of 1127 parseable
  mined pairs (99.2%) and parses 90.1% of 1251; the 9 disagreements are author typos or condition-dependent lines.
  Rare relations are small in dev (implies 8, narrows 6, unparsable 12) and smaller in test (4, 2, 5). Test split
  not run.
- 2026-10-27 | parse_input | dev, SUBSET 15 of 170 (taken in turn from each kind) | case_accuracy=0.933 (baseline; 14 of 15) | e42d774 | Model
  `nvidia/nemotron-3.5-super-vl:free`, prompt hash cd937f44ed21. failure_rate 0, sympy_parse_rate 1.0, no_working_accuracy 1.0
  (7 cases), claim_recall_canonical 0.882 (15 of 17 claims; strict equals canonical). Both deliberately wrong steps were
  transcribed unchanged. The one miss (`full`, `expression`, `connectors`, `unicode`): the model kept the first step inside the
  problem (`((1/2))^3 . (1/2)*(1/2)*(1/2)`) and so dropped it as a step; the lone `.` the renderer puts between the problem
  and the first step may have read as a multiplication dot (a guess). Partly an ambiguous message, partly a prompt gap. n=15, so the 95% Wilson interval for 14/15 is about 0.70-0.99:
  a smoke check, not an estimate. Not tuned on this miss; the full dev run is the next step. Result file:
  `evals/results/parse_input/20261027T132533Z_e42d774.json`.
- 2026-10-27 | classify | dev, SUBSET 15 of 420 (taken in turn from each subject) | topic_accuracy=0.667 (baseline; 10 of 15), in_scope_accuracy=0.800, level_accuracy=0.133, level_within_one=0.533 | b178d94 | Model
  `nvidia/nemotron-3.5-super-vl:free`, prompt hash 96a9483b4d2f, failure_rate 0. Per-subject recall: 1.0 for Algebra, Counting &
  Probability, Number Theory, Precalculus; 0.5 Geometry; 0.0 Intermediate Algebra and Prealgebra (2 problems each). The 5 misses
  are mostly fuzzy MATH labels: a probability problem labelled Geometry, two counting-flavoured problems labelled Intermediate
  Algebra (both sent to Counting & Probability, i.e. out of scope), a linear inequality labelled Prealgebra (sent to Algebra), and a
  "how many integers divisible by 2, 3 and 5" labelled Prealgebra (sent to Number Theory). So topic accuracy against MATH's labels
  understates the model, but in-scope problems that land out of scope are the cost that matters (3 of 15). Levels: 8 of the 15 are
  level 5 by chance and the model rarely says 5, so the level numbers are pessimistic; no node reads `level` yet. n=15 is a smoke
  check (95% interval for 10/15 is about 0.42-0.85). Not tuned on these misses. Result file:
  `evals/results/classify/20261027T134021Z_b178d94.json`.
- 2026-10-27 | localize | dev | case_accuracy=1.000 (baseline; n=78, generated 1.000, handwritten 1.000) | 178cc20 | Deterministic
  (`verify` then `localize`, no model). first_error_step, focus_step and error_type accuracy all 1.000, mismatch_detection_rate
  1.000, no confusions. A regression suite, not independent evidence: the generated cases are correct by construction and were
  selected with `verify`, and the 35 hand-written labels were worked out by reading and agree with the pipeline (about ten were
  probed with `verify` first; the lost-solution label was revised, see above). Dev has few hand-written cases per type (4
  mismatch, 2 omission, 3 other, 1 control). Test split not run. Result file:
  `evals/results/localize/20261027T141132Z_178cc20.json`.
- 2026-10-27 | retrieve | dev | recall@1=0.898, recall@5=0.978, map@5=0.931 (baseline; n=324; random 0.008 / 0.042) | 859537a | Mean of
  string similarity and embedding cosine (MiniLM) on the shape of what changed (the lines trimmed of what they share,
  variables to `v`, numbers to `n`). Per source (recall@1 / recall@5): handwritten (20) 0.900 / 0.950, generated_wrapped
  (100) 0.820 / 0.980, generated (204) 0.936 / 0.980. The plain generated number is close to a lookup (89 of 99
  rules give the example's own shape); quote the other two. Lowest recall@1 by category: absolute_value 0.32 (19),
  squaring_extraneous 0.50 (12), solving_equations 0.84 (44), quadratics 0.85 (26). The first design (embed the
  description plus example, query with topic, error type and raw lines) scored recall@1 0.16 on dev and was replaced after
  dev-only experiments (`docs/decisions.md`). Caveats: circular (one author for catalogue and queries), 20
  hand-written queries, and the test split is no longer untouched (its aggregate scores were seen once and a reviewer
  looked at its misses); test not run. Result file: `evals/results/retrieve/20261027T155456Z_859537a.json`.

- **M5 layer 2, `retrieve` abstention (2026-10-27)**: `MIN_SCORE = 0.85`; below it `misconception` is None (the
  candidates stay). Dev (324): answered 0.914, precision of the answered 0.959; recall is unchanged (0.898 / 0.978).
  Dev top-1 scores: every one is at least 0.71 and most right ones are 1.0, so the dev set cannot show where wrong
  matches separate; 0.85 is a coverage-biased guess, not a measured optimum (t=0.90 would give 0.87 / 0.982). Real
  off-catalogue steps are missing from the data, so quote these numbers as optimistic. Result file:
  `evals/results/retrieve/20261027T161743Z_3cd8c9f.json`.

- **M5 layers 3-5, `hint` (2026-10-27)**: `hint` node, SymPy counterexample, leakage check, canned hints, eval. Dev, 15 of 60
  cases (`--limit`, in turn over the levels), gold misconception: leakage 0.067 (1 case, level 4: "x * x = x^2", the general
  rule applied to a problem that is itself the rule, so it also writes the corrected line; counted as a leak), counterexample
  numbers used by the hint 1.000 (level 2, n=4), judge pass rates praise/Socratic/on-target 1.000 and fits-level 0.833 (n=12
  judged). **Failures: 2 of 15 hints fell back to the canned hint (0.133) and 3 of 15 judge calls failed (0.200), all
  HTTP 429 rate limits from the free model; a rerun hit the same limits.** The rates over the judged cases are
  therefore from 12 cases and are not reliable; the judge is the same model as the writer and gave no failing grade on
  praise, Socratic or on-target, so it is likely lenient. Read by hand: hints are on target and use only given numbers;
  the praise is a generic "thanks for trying" at every level. Next: the human check of the 20-hint sample file (fill
  `human_ok`), a full dev run when the rate limit allows, then the test split once (the developer builds
  `test/hint.jsonl`). Result: `evals/results/hint/20261027T163059Z_6271572.json` (+ `_samples.jsonl`).

- **M6 layers 1-4, orchestration (2026-10-27)**: learner DB tools, `orchestrator` (three modes), SQLite checkpointer,
  scenarios A and B as YAML with a replay runner, `eval_orchestrator.py`. **No live metrics yet.** With the model
  scripted, both scenarios replay through the real graph (real verify, localize, leakage check, checkpointer and learner
  DB) and meet every expectation: A asks for steps, hints at level 1, then records a correct solution and offers
  practice at the third occurrence; B hints at levels 1, 2 and 1 (the level resets for the new misconception) and ends
  correct. That checks the wiring and the rules, not the model. The live replay was started and stopped: the free
  model returned HTTP 429 on every orchestrator call, which fell back to the step rule, so its numbers would mean
  nothing; no result file was written. The routing eval has no dataset: 32 unlabelled candidate turns are in
  `evals/datasets/review/orchestrator_candidates.jsonl` for the developer to label. Next: label the candidates
  (`dev/orchestrator.jsonl`), run `--part routing` and `--part scenarios` when the rate limit allows, then fill in
  this entry with the numbers.

## Deployment
- **M7 app (2026-10-27)**: Streamlit chat (`app.py`, `src/tutor/ui.py`): name field, chat bubbles on the checkpointed
  history, "New chat" (same person, same profile), sidebar with hint level, hints used and the `get_profile` summary,
  a visited-nodes toggle. Unit tests (`test_ui.py`, `test_app.py` with Streamlit's `AppTest`) run with the model scripted.
  No metrics: the app is not a node. **Not done yet: the demo video, the report and the single test-split run.**
- Planned: the demo video using scenarios A and B.
