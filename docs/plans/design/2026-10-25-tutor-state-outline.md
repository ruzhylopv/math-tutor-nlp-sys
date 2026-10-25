# Plan: TutorState outline (approved 2026-10-25; revised by the design-gaps plan; no code yet)

Outline for the future `src/tutor/state.py`, which stays the single source of truth for data shapes.
Nothing here is implemented. Items marked OPEN need a decision before the code is written.

## TutorState (TypedDict, total=False)
| Field | Meaning | Written by |
|---|---|---|
| messages | chat history, appended (`add_messages`); a hint enters it only after the leakage check | orchestrator, UI |
| problem | problem text | parse_input |
| student_steps | list of `Step` | parse_input |
| topic, level | topic label, difficulty | classify |
| is_correct | final answer matches ground truth | verify |
| step_verdicts | list of `StepVerdict` | verify |
| first_error_step | 1-based index or None | localize |
| focus_step | 1-based step that retrieval and the hint talk about; equals `first_error_step` when that exists, otherwise the step that caused the problem (for `omission_extraneous_root`, the non-reversible step) | localize |
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
| student_id | name typed in a login-style field in the Streamlit UI; identifies, does not authenticate | UI |
| learner_profile | weak topics, past misconceptions | orchestrator (via `get_profile`) |

Settled additions (2026-10-25):
- `focus_step`: written by `localize`.
- `problem`: extracted by a separate LLM node, `parse_input`, which structures the student's text into the
  state. Input is text only for now (photos would need a vision/OCR model first). `verify` parses `problem`
  into a SymPy equation with a restricted parser.
- `justification_claim` on `Step`: the claimed equation behind a free-text justification (for example "-2 + -9 = 11"
  for "add to 11"), filled by the node that splits the steps (`parse_input` in the proposal) and evaluated by
  SymPy in `verify`.
- `student_id`: the name typed into a login-style field in the Streamlit UI.

OPEN: the boundary between `parse_input` and `classify`, and where `parse_input` sits. Proposal: `parse_input`
takes the problem and the step structure, `classify` only tags topic and level, and `parse_input` is the first
node of the diagnosis subgraph so that pure questions cost no extra LLM call.

## Pydantic models
- `Step`: claim (math expression or equation), justification (text, may be empty), justification_claim (optional), operation tag
  (expand / rearrange / factor / zero-product / substitute / square / other).
- `StepVerdict`: step index; relation to the previous step (equivalent / implies / not_valid /
  unparsable); justification_claims_ok (bool or None); notes.
- `Decision`: action (ask / diagnose / hint / reply), reason, reply_text (optional).
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
