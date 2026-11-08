# Plan: hint answers replies and stopped solutions; orchestrator routes replies (approved 2026-11-08)

Layer 5 of `docs/plans/design/2026-11-02-flexible-input.md`. Evals are debt for layers 4-6. Stacked on #81,
because #81 alone makes `hint` call a correct line wrong.

## hint (node and prompt)
- `incomplete`: the prompt says the work so far is correct and gives the last valid line; no counterexample and
  no misconception. Intent `stuck`: point at the next step from that line. Otherwise confirm the work and ask
  what comes next.
- Intent `answer`: also gets the tutor's last message and the student's reply, responds to the reply first and
  returns `reply_moves_forward`. The leak check is unchanged.

## orchestrator (node and prompt)
- The prompt gets `intent` and the tutor's last message.
- Enforced in code when a diagnosis exists and the intent is `answer`: no math line goes to `hint` without an LLM
  routing call; a math line goes to `diagnose`, so SymPy checks it.
- Level: a reply never raises the level for its own hint, because the verdict exists only after the hint is
  written. The verdict sets the next one: False goes up by one, True or no verdict stays.
- Resubmitted partial progress (`incomplete`) does not raise the level unless the student says they are stuck.

## Also
- `new_turn` resets `intent`, so a failed parse cannot reuse the last turn's intent.
- Shared message helpers move to `tools/messages.py`.
- CLAUDE.md names the exception to the math rule (developer approved the line).
