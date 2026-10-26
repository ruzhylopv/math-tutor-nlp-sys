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
- 2026-10-25 | Eedi | A paper reports 1,857 questions; the number of distinct misconceptions and
  whether the scenario A/B misconceptions exist in it are unverified.

## Data preparation
- Planned, not started: convert each source to the per-component JSONL format; fixed dev/test splits.
- 2026-10-26 | verify_steps | Built `evals/datasets/{dev,test}/verify_steps.jsonl` from MATH Algebra levels 1-3 (mined
  identity pairs), rule-based corruptions with a witness guard, and 76 hand-written cases. Dev 1621, test 671, review 9.
  Format and limits: `evals/datasets/README.md`.

## Modeling
- Planned build order: verify, classify, localize, retrieve, hint, orchestrator + graph, checkpointer
  + scenarios, Streamlit UI.
- 2026-10-25 | M1 skeleton | State models, config, the OpenRouter client, the shared eval runner, eight stub
  nodes, the diagnosis subgraph and the main graph compile and pass 83 unit tests; `docs/graph.mmd` is the
  Mermaid export. No model has been called yet: `scripts/check_llm.py` is the next step to run by hand once
  `MODEL_NAME` is chosen. Plan: `docs/plans/design/2026-10-25-m1-skeleton.md`.

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

## Deployment
- Planned: runnable Streamlit app and a demo video using scenarios A and B.
