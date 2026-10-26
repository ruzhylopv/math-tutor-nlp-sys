# Plan: M3 input layer, `parse_input` and `classify` (approved 2026-10-26)

Goal: the two LLM nodes that turn a student's text into our structure. `parse_input` extracts the problem and
the steps (plain-text math, which `verify` needs); `classify` tags the topic and level. Both use structured
output. Roadmap: `docs/plans/design/2026-10-25-roadmap.md`.

## Decisions (from the developer)
- `parse_input` sits in the main graph between the UI and the orchestrator (START -> parse_input ->
  orchestrator). Every message passes through it, so a pure question also costs one LLM call. The diagnosis
  subgraph now starts at `classify`.
- `topic` is one of the MATH subjects, `level` is MATH's 1-5. The in-scope subjects are Prealgebra, Algebra and
  Intermediate Algebra; the others let `classify` act as a scope guard.
- No limit on dataset size; retries and a cache keep a long eval run alive under rate limits.
- The committed `verify` datasets are not rebuilt.
- Text input only.

## Decisions (agent defaults, approved with the plan)
- `parse_input` resets `student_steps` to an empty list for a message without working (so steps from the previous
  attempt are not mistaken for a new one) and keeps the stored `problem` when the message has none.
- Faithfulness first: the node transcribes, it never repairs the student's math. The metric is a normalized exact
  match of each claim, not equivalence (SymPy's parser would distribute `3(x+2)` into `3x+6` and hide the difference).
- If the model returns something invalid twice, `parse_input` returns no steps and no problem (the orchestrator
  then asks the student to resend); `classify` returns the out-of-scope default and records the failure. Neither
  raises.
- Prompts are loaded from `src/tutor/prompts/*.md`; no example is copied from an eval dataset.
- LLM calls go through one function in `src/tutor/tools/`, which tests mock, so no node touches the network.

## Stack
0. `chore/m3-plan`: this plan, the decisions, the architecture and graph docs, the datasets README status.
1. `feat/llm-tools`: the prompt loader and `tools/structured.py` (one structured call, one retry, a small cache
   for evals), with tests that mock the client.
2. `feat/classify`: prompt, node, tests, eval script and the MATH-label dataset.
3. `feat/parse-input`: prompt, node, tests, eval script and the dataset (see open items).
4. `feat/input-wiring`: `parse_input` before the orchestrator, `classify` first in the diagnosis subgraph, tests and
   the redrawn `docs/graph.mmd`.

## Data
- `classify`: MATH's own subject and level labels (12,500 problems: Algebra 2,931, Prealgebra 2,076, Intermediate
  Algebra 2,198, Geometry 1,350, Number Theory 1,409, Precalculus 1,291, Counting & Probability 1,245), human-assigned
  and independent of our code. Dev and test are stratified by subject, split by problem with a fixed seed.
  Metrics: topic accuracy and macro-F1, level accuracy and within-one.
- `parse_input`: no public set of student messages. Default source: messages rendered from the step chains already
  mined from MATH (labels known by construction), hand-written scenario A and B messages, and cases with no steps or no
  problem. Metrics: problem-extraction accuracy, claim exact match (normalized), step-split accuracy, SymPy parse rate
  of the claims.

## Open
- Which messiness features the `parse_input` messages include (numbered steps, words between lines, unicode math,
  LaTeX, spelled-out math, typos): to be decided with the developer before layer 3.
- The size and the split of the `parse_input` dataset.
- The model name, to be recorded with the first eval result.

## Risks
- The model "fixes" a student's mistake while transcribing: the eval targets exactly this.
- Free-model latency and rate limits: measure a structured call first.
- Structured output failing on a free endpoint: `scripts/check_llm.py` before each eval run.
