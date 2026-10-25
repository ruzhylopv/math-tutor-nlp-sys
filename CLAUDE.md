# Math tutor: agent rules

## Project
LangGraph math tutor for school algebra. Student submits a problem + step-by-step solution;
the system verifies steps (SymPy), localizes the error, retrieves the misconception, and gives
graded Socratic hints without revealing the answer. Architecture: docs/architecture.md.

## Where things live
- src/tutor/state.py: TutorState + pydantic models (single source of truth for data shapes)
- src/tutor/nodes/: one file per graph node
- src/tutor/prompts/: one .md file per LLM node
- src/tutor/tools/: SymPy checks, learner DB
- evals/: datasets (dev/ and test/ splits), scripts, results, scenarios
- docs/: architecture, decisions log, CRISP-DM log, approved plans

## Workflow (always follow)
1. Any change touching more than one file: propose a plan first and wait for approval.
   Save the approved plan to docs/plans/YYYY-MM-DD-<topic>.md.
2. Work on one component per session. Do not modify other nodes unless the plan says so.
3. Keep diffs small. Ask before adding or removing dependencies.
4. Before saying a task is done, run:
   `uv run ruff check . && uv run mypy src && uv run pytest -q`
5. Commit with conventional messages (feat:, fix:, test:, chore:, docs:). Never push.
6. Record any design choice with an alternative you rejected in docs/decisions.md.

## Code rules
- Node contract: a node is a pure function `(TutorState) -> dict` returning only the fields it changed.
  No module-level state, no hidden I/O except through src/tutor/tools/.
- The LLM never does arithmetic or checks algebra. All math verification goes through SymPy.
- Prompts are loaded from src/tutor/prompts/*.md. Never write a prompt inline in Python.
- LLM outputs that drive logic must use structured output (pydantic model), not string parsing.
- Use LangGraph only for orchestration. Do not use classic LangChain chains.
- Type hints on every function. Use `logging`, not `print`.
- No secrets in code. Config comes from .env via src/tutor/config.py.

## Tests and evaluation
- Every node has unit tests that run without network: mock the LLM.
- Every node has an eval script in evals/scripts/ that writes metrics to evals/results/.
- Iterate on prompts and logic using the dev split only. The test split is for final reported numbers.
- Never edit eval datasets, expected labels, or existing tests to make results pass.
  If you believe a label or test is wrong, stop and tell me.
- Never tune a prompt with examples copied from the eval datasets.

## When unsure
State your assumption and ask. Do not invent dataset formats, API details or library behaviour;
check the installed package or tell me you are unsure.

## Definition of done for a component
- [ ] Implementation follows the node contract
- [ ] Unit tests pass
- [ ] Eval script runs and a metrics file exists in evals/results/<component>/
- [ ] docs/crisp_dm_log.md has an entry for this iteration
- [ ] Committed