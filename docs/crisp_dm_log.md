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
- 2026-10-25 | Eedi | A paper reports 1,857 questions; the number of distinct misconceptions and
  whether the scenario A/B misconceptions exist in it are unverified.

## Data preparation
- Planned, not started: convert each source to the per-component JSONL format; fixed dev/test splits.

## Modeling
- Planned build order: verify, classify, localize, retrieve, hint, orchestrator + graph, checkpointer
  + scenarios, Streamlit UI.
- 2026-10-25 | M1 skeleton | State models, config, the OpenRouter client, the shared eval runner, eight stub
  nodes, the diagnosis subgraph and the main graph compile and pass 64 unit tests; `docs/graph.mmd` is the
  Mermaid export. No model has been called yet: `scripts/check_llm.py` is the next step to run by hand once
  `MODEL_NAME` is chosen. Plan: `docs/plans/design/2026-10-25-m1-skeleton.md`.

## Evaluation
<!-- Format: YYYY-MM-DD | <component> | <split> | <key metric>=<value> (change) | <git-hash> | note -->
- No evaluations yet.

## Deployment
- Planned: runnable Streamlit app and a demo video using scenarios A and B.
