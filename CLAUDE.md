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
   Save the approved plan to docs/plans/<area>/YYYY-MM-DD-<topic>.md
   (area: workflow, design or nodes).
2. Work on one component per session. Do not modify other nodes unless the plan says so.
3. Keep diffs small. Ask before adding or removing dependencies.
4. Before saying a task is done, run:
   `uv run ruff check . && uv run mypy && uv run pytest -q`
5. Commit with conventional messages (feat:, fix:, test:, chore:, docs:).
6. Record any design choice with an alternative you rejected in docs/decisions.md.

## Branches and pull requests (always follow)
Every change reaches `main` through a reviewed PR. The developer reviews and merges; agents do not.
- Never commit or push on `main`. Start each feature on a branch: `feat/<topic>`, `fix/<topic>`,
  `chore/<topic>`, `docs/<topic>`, `test/<topic>`.
- One PR per feature, using `.github/pull_request_template.md`. Use the `open-pr` skill.
- Split into a stack when the work has more than one logical concern or is about 400+ changed
  lines (e.g. state + node + graph wiring, or implementation + eval). Use the `gh-stack` skill:
  one concern per layer, dependencies in lower layers.
- Pushing is allowed for feature branches only. Never push `main`, never force-push, never merge
  a PR (`gh pr merge`, `gh stack merge` are denied).
- After opening a PR, run the `review-loop` skill: reviewer subagent, then fixer subagent, at most
  2 passes. Findings are graded P0 (blocker), P1 (critical), P2 (should fix), P3 (nit). P0 and P1
  must be resolved or escalated in the PR; P3 is reported, not fixed.
- When the developer requests changes on a PR (or submits a comment review starting with `/address-review`), the `address-review` workflow (GitHub Actions) runs the
  `address-review` skill on that PR's branch. It is limited to the developer's account and never merges.
- The plan gate (rule 1) still applies. A plan is approved in chat before any code is written.

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
  Exception: `finish_diagnosis` (a deterministic marker node with nothing to measure) needs unit tests only.
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