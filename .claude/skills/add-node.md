---
name: add-node
description: Scaffold a new LangGraph node for the math tutor (node file, prompt, unit test, eval stub, graph wiring). Use when the user asks to add, create or start a new node or component.
---

# Add a node

Use this to start a new component. It sets up the scaffolding; it does not implement the real logic.

## Inputs to confirm before starting
Ask for anything missing. Do not guess:
1. Node name (snake_case, e.g. `localize`).
2. Is it an LLM node or a deterministic node (SymPy, retrieval, DB)?
3. Which `TutorState` fields it reads and which it writes.
4. Where it sits in the graph: main graph or diagnosis subgraph, incoming edge, outgoing edge(s).
5. Its evaluation metric and which dataset it will use.

## Step 1: Plan
Write a short plan listing every file you will create or change and the state fields involved.
Wait for approval, then save it to `docs/plans/YYYY-MM-DD-add-<name>.md`.

## Step 2: State
If the node writes new fields, add them to `TutorState` in `src/tutor/state.py` with type hints.
Add a pydantic model there if the node produces structured data. Do not rename or remove existing
fields without asking.

## Step 3: Node file: `src/tutor/nodes/<name>.py`
- One public function `<name>(state: TutorState) -> dict` that returns only the fields it writes.
- A docstring with: purpose, fields read, fields written, eval metric.
- For now the body returns fixed placeholder values that match the declared types, marked `# TODO`.
- LLM nodes: load the prompt from `src/tutor/prompts/<name>.md`, use structured output with a pydantic
  model, and no inline prompt text.
- Deterministic nodes: any math goes through `src/tutor/tools/`, never through an LLM.

## Step 4: Prompt (LLM nodes only): `src/tutor/prompts/<name>.md`
Create it with sections: Role, Inputs, Task, Output format, Rules. Fill only Role and Output format;
leave the rest as TODO. Never copy examples from `evals/datasets/`.

## Step 5: Unit tests: `tests/test_<name>.py`
At minimum:
- the node returns only keys that exist in `TutorState` and only the fields it declares;
- returned values have the declared types;
- for LLM nodes, the LLM is mocked, and no network is used.

## Step 6: Eval stub: `evals/scripts/eval_<name>.py`
- Reads `evals/datasets/dev/<name>.jsonl` by default, `--split test` only when asked.
- Calls the node function directly (not the whole graph).
- Computes the agreed metric and writes results using the shared eval runner.
- If the dataset does not exist yet, do not create fake labels. Leave the script ready and note
  in the summary that the dataset is missing.

## Step 7: Graph wiring: `src/tutor/graph.py`
Register the node and add its edges as agreed in the plan. Do not change unrelated edges.

## Step 8: Docs and checks
1. Add the node to `docs/architecture.md` (one line: purpose, reads, writes).
2. Run `uv run ruff check . && uv run mypy src && uv run pytest -q`; fix failures.
3. Run `uv run python scripts/draw_graph.py` if it exists, and confirm the node appears.
4. Commit: `feat(<name>): scaffold node`.

## Final summary to the user
List the files created and changed, the state fields added, and what is still a TODO.