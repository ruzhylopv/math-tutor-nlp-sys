# Plan: turn the design handoff into docs (approved 2026-10-25)

Source: the planning handoff from the chat outside this repo. Docs only; no code, no dependency changes.

## Files
- `docs/architecture.md` (new)
- `docs/decisions.md` (append)
- `docs/crisp_dm_log.md` (new)
- `docs/plans/design/2026-10-25-tutor-state-outline.md` (new; the TutorState plan, not code)

## Answers to the OPEN questions
- LLM: OpenRouter, a free model (the developer will not pay for tokens). Dependency swap deferred.
- Retrieval: in-memory sentence-transformers + FAISS (approval needed when added).
- Target level: provisional, MATH Algebra levels 1-3. Superseded 2026-10-26, see M3 decisions in `docs/decisions.md`.
- `localize`: rules first, LLM only for interpretation.
- Leakage check: a function in `src/tutor/tools/`, called by the orchestrator.
- Learner DB: SQLite, `attempts` and `misconceptions_seen`.
- Gaps found while writing (leakage failure path, `focus_step`, `student_id`, Eedi mapping) are
  recorded as OPEN items in `docs/decisions.md`.
