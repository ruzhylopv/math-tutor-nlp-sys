# Plan: TutorState outline (approved 2026-10-25; revised by the design-gaps plan; no code yet)

Outline for the future `src/tutor/state.py`, which stays the single source of truth for data shapes.
Nothing here is implemented. Items marked OPEN need a decision before the code is written.

## TutorState (TypedDict, total=False)
| Field | Meaning | Written by |
|---|---|---|
| messages | chat history, appended (`add_messages`); a hint enters it only after the leakage check | orchestrator, UI |
| problem | problem text | orchestrator |
| student_steps | list of `Step` | classify |
| topic, level | topic label, difficulty | classify |
| is_correct | final answer matches ground truth | verify |
| step_verdicts | list of `StepVerdict` | verify |
| first_error_step | index or None | localize |
| error_type | see below | localize |
| misconception_candidates | ranked list of `Misconception` | retrieve |
| misconception | top chosen misconception | retrieve |
| hint_level | int 1-4, per current misconception | orchestrator |
| hint_text | the hint just generated, not yet published | hint |
| hint_retries | leakage-check retries for the current hint (cap 1) | orchestrator |
| stage | `new_message` / `diagnosed` / `hinted`; selects the orchestrator's mode | UI (new_message), `finish_diagnosis` (diagnosed), hint (hinted) |
| reply_text | text sent to the student | orchestrator |
| turns, hints_used | counters for `record_attempt` | orchestrator |
| misconceptions_seen | misconception ids diagnosed in this attempt; the last entry is the stored id used to reset or escalate `hint_level` | orchestrator |
| next_action | ask / diagnose / hint / reply | orchestrator |
| learner_profile | weak topics, past misconceptions | orchestrator (via `get_profile`) |

OPEN additions (not in the handoff):
- `focus_step`: for `omission_extraneous_root`, `first_error_step` is None but `retrieve` and `hint`
  need a step to talk about (the "implies" step, for example the squaring). Proposal: `localize`
  writes `focus_step`.
- `problem` extraction: who pulls the problem text out of the first message, and who parses it into a SymPy
  equation. Proposal: an optional `problem_text` on `Decision`; `verify` parses it with a restricted parser.
- `justification_claim`: who turns free-text justifications such as "add to 11" into a checkable claim.
  Proposal: an optional `justification_claim` on `Step` (the claimed equation), filled by `classify`, evaluated
  by SymPy in `verify`.
- `student_id`: the checkpointer is keyed by `thread_id`, but the profile spans sessions, so the
  learner DB needs a student identity. Proposal: a name field in the Streamlit UI.

## Pydantic models
- `Step`: claim (math expression or equation), justification (text, may be empty), (OPEN) justification_claim, operation tag
  (expand / rearrange / factor / zero-product / substitute / square / other).
- `StepVerdict`: step index; relation to the previous step (equivalent / implies / not_valid /
  unparsable); justification_claims_ok (bool or None); notes.
- `Decision`: action (ask / diagnose / hint / reply), reason, reply_text (optional), (OPEN) problem_text (optional).
- `Misconception`: id, description, topic, score.

## Error types
`algebraic_transformation`, `omission_extraneous_root` (first_error_step = None),
`reasoning_result_mismatch` are produced by `localize`. `final_answer_only` is not: `classify` finds zero steps and
the orchestrator routes to `ask`. Definitions are in `docs/architecture.md`. Step numbers are 1-based; step 1's
predecessor is the problem statement.

## Learner DB (SQLite) draft
- `attempts(id, student_id, problem, topic, level, turns, hints_used, solved, created_at)`
- `misconceptions_seen(id, attempt_id, misconception_id, error_type, focus_step)`
- `get_profile(student_id)` aggregates these: weak topics, misconception counts.
- `record_attempt(...)` inserts one attempt and its misconceptions.
The path comes from `LEARNER_DB_PATH` in `.env`. Column details are reviewed when the tool is built.
