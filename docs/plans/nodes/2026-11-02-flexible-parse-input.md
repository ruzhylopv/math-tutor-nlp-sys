# Plan: parse_input reads line kinds, intent and topic (approved 2026-11-02)

Layer 2 of `docs/plans/design/2026-11-02-flexible-input.md`.

## Changes
- **Node** (`src/tutor/nodes/parse_input.py`): passes the tutor's last message (the last `AIMessage`
  before the latest student message, or "none") to the model as a third labelled input. Always writes
  `intent`. Writes `topic` and `level` only when the message states a problem; a question about the
  stored problem keeps the stored topic.
- **Prompt** (`src/tutor/prompts/parse_input.md`): `kind` per line (equation / definition / reason /
  check / other), the intent labels (`answer` = a reply to the tutor's last question), the subject and
  level descriptions moved from `classify.md`. Rules in general terms; no example from the eval sets.
- **Eval** (`evals/scripts/eval_parse_input.py`): adds `kind_accuracy` (per line, over cases with
  expected kinds) and `intent_accuracy` (over cases with an expected intent); adds `topic/accuracy`,
  `topic/macro_f1`, `topic/level_within_one`, `topic/failure_rate` by running the classify dev problems
  through parse_input as messages. `--limit N` applies to each dataset.
- **Dataset**: 12-15 hand-written dev cases `flex/NNN` (substitution, reasons in words, mixed prose and
  math, stuck, replies to a tutor question, explain, new problem), `spot_check: pending`, appended to
  `dev/parse_input.jsonl` only. No existing line changes; the test split is not touched.
- **Tests**: node (tutor message passed, intent written, topic kept or replaced) and new eval metrics,
  LLM mocked.
- **Docs**: architecture parse_input row, CRISP-DM log entry, decisions entry.

## Deviation from the design plan
`classify` (node, prompt, eval, tests) stays in the graph until layer 6. Removing it now touches
`graph.py`, `ui.py` and four test files, which is layer 6's scope. Cost: for one layer classify still
runs after parse_input and overwrites its topic (one extra LLM call per diagnosis).
