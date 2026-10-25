# CRISP-DM log

CRISP-DM is applied twice: once for the whole project, and as a small loop per node (explore data,
build, evaluate, iterate). Evaluation entries are appended by the `run-eval` skill under
**Evaluation**.

## Business understanding
- 2026-10-25 | project | Students repeat the same algebra mistakes; generic chatbots give the answer
  away or cannot say why the student went wrong. Success = correct diagnosis and helpful hints
  without answer leakage. Scope and architecture: `docs/architecture.md`.

## Data understanding
- Planned, not started: explore MATH, GSM8K, ProcessBench / PRM800K and Eedi; note gaps that need
  hand-made sets (equivalence vs implication, reasoning-result mismatch, routing). Verify each
  source's format and licence first.

## Data preparation
- Planned, not started: convert each source to the per-component JSONL format; fixed dev/test splits.

## Modeling
- Planned build order: verify, classify, localize, retrieve, hint, orchestrator + graph, checkpointer
  + scenarios, Streamlit UI.

## Evaluation
<!-- Format: YYYY-MM-DD | <component> | <split> | <key metric>=<value> (change) | <git-hash> | note -->
- No evaluations yet.

## Deployment
- Planned: runnable Streamlit app and a demo video using scenarios A and B.
