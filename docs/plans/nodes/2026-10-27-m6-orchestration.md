# Plan: M6 orchestration (approved 2026-10-27)

Goal: the orchestrator (three modes), the learner DB tools, the checkpointer and scenario replays A and B.
Roadmap: `docs/plans/design/2026-10-25-roadmap.md`. M1-M5 are merged.

## Decisions (from the developer)
- Out-of-scope subject: after diagnosis, reply with a fixed decline and end; no hint, no `record_attempt`.
  Rejected: hinting anyway (the catalogue is algebra-only, so hints would be generic).
- Checkpointer: `langgraph-checkpoint-sqlite` (new dependency, approved). Rejected: `InMemorySaver` only (state lost on
  restart).
- Scenarios: YAML with per-turn expectations; `pyyaml` declared as a direct dependency (approved). Rejected: JSON.
- Reset on a changed problem: clear `hint_level`, `hint_retries`, `error_context`, `misconception`,
  `misconceptions_seen`, `step_verdicts`, `stage`, `first_error_step`. Rejected: carrying `misconceptions_seen`
  across problems (it would mix the hint-level escalation).
- Practice offer when the profile count for the misconception reaches 3. Wording: "You've made this kind of mistake a
  few times. Want a few practice problems on <description>?"
- Routing dev set of about 30 hand-labelled turns: candidates are drafted and the developer labels and reviews them.

## Layers (a stack of PRs, lowest first)
1. **`feat/m6-learner-db`**: `tools/learner_db.py` (SQLite; `get_profile`, `record_attempt`; tables from the state
   outline; path from `LEARNER_DB_PATH`), `LearnerProfile` finalised in `state.py`, unit tests on a temp DB.
2. **`feat/m6-orchestrator`**: the `orchestrator` node and `prompts/orchestrator.md`.
   - new_message: LLM `Decision`; no steps means `ask`; a question without an attempt means `hint` with
     `hint_level` + 1 (cap 4); `turns` in plain code; reset points above.
   - diagnosed: out-of-scope decline; clean solution calls `record_attempt` and offers practice; otherwise a different
     misconception id resets `hint_level` to 1, the same id adds 1 (cap 4), append to `misconceptions_seen`, route to
     `hint`.
   - hinted: `find_leaks`; pass publishes the hint (`messages`, `hints_used`, `reply_text`); leak retries once, then
     `canned_hint(level)`. A rejected hint never enters `messages`.
3. **`feat/m6-graph-checkpointer`**: `build_main_graph(checkpointer=...)`, a SQLite saver factory in `tools/`,
   `stage = new_message` at the start of a run, regenerated `docs/graph.mmd`.
4. **`test/m6-scenarios`**: `evals/scenarios/{a,b}.yaml`, a scenario runner with mocked-LLM unit tests, and
   `eval_orchestrator.py` (routing accuracy on `evals/datasets/dev/orchestrator.jsonl`; live replay of A and B).
5. **`docs/m6`**: `docs/decisions.md`, CRISP-DM entry, `architecture.md` OPEN items marked DECIDED.
