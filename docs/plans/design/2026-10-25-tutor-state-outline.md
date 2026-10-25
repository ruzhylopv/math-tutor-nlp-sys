# Plan: TutorState outline (approved 2026-10-25; no code yet)

Outline for the future `src/tutor/state.py`, which stays the single source of truth for data shapes.
Nothing here is implemented. Items marked OPEN need a decision before the code is written.

## TutorState (TypedDict, total=False)
| Field | Meaning | Written by |
|---|---|---|
| messages | chat history, appended (`add_messages`) | orchestrator, UI |
| problem | problem text | orchestrator |
| student_steps | list of `Step` | classify |
| topic, level | topic label, difficulty | classify |
| is_correct | final answer matches ground truth | verify |
| step_verdicts | list of `StepVerdict` | verify |
| first_error_step | index or None | localize |
| error_type | see below | localize |
| misconception_candidates | ranked list of `Misconception` | retrieve |
| misconception | top chosen misconception | retrieve |
| hint_level | int, per current misconception | orchestrator |
| next_action | ask / diagnose / hint / reply | orchestrator |
| learner_profile | weak topics, past misconceptions | orchestrator (via `get_profile`) |

OPEN additions (not in the handoff):
- `focus_step`: for `omission_extraneous_root`, `first_error_step` is None but `retrieve` and `hint`
  need a step to talk about (the "implies" step, for example the squaring). Proposal: `localize`
  writes `focus_step`.
- `student_id`: the checkpointer is keyed by `thread_id`, but the profile spans sessions, so the
  learner DB needs a student identity. Proposal: a name field in the Streamlit UI.

## Pydantic models
- `Step`: claim (math expression or equation), justification (text, may be empty), operation tag
  (expand / rearrange / factor / zero-product / substitute / square / other).
- `StepVerdict`: step index; relation to the previous step (equivalent / implies / not_valid /
  unparsable); justification_claims_ok (bool or None); notes.
- `Decision`: action (ask / diagnose / hint / reply), reason, reply_text (optional).
- `Misconception`: id, description, topic, score.

## Error types
`algebraic_transformation`, `omission_extraneous_root` (first_error_step = None),
`reasoning_result_mismatch`, `final_answer_only`. Definitions are in `docs/architecture.md`.

## Learner DB (SQLite) draft
- `attempts(id, student_id, problem, topic, level, turns, hints_used, solved, created_at)`
- `misconceptions_seen(id, attempt_id, misconception_id, error_type, focus_step)`
- `get_profile(student_id)` aggregates these: weak topics, misconception counts.
- `record_attempt(...)` inserts one attempt and its misconceptions.
The path comes from `LEARNER_DB_PATH` in `.env`. Column details are reviewed when the tool is built.
