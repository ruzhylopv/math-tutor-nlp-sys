# Plan: a calculation in reply to a hint (approved 2026-11-08)

Found in a real chat: after a hint, the reply `-2 * -3 = -6` went through a full diagnosis as if it were a new attempt. `localize`
and `retrieve` overwrote the real diagnosis, `error_context` came back empty, and `hint` returned the canned text.

Intended flow: the math goes to `diagnosis`; back in the orchestrator, the result is read as a response to the tutor's own hint,
and another hint follows.

- `tools/diagnosis.is_calculation_reply`: intent `answer`, an existing `error_context`, and every line a closed statement.
- `route_after_verify`: such a reply ends the subgraph after `verify`, so the focus step and misconception stay.
- `orchestrator`, `diagnosed` mode: such a reply goes to `hint` and keeps `error_context` and `hint_level`.
- `hint`: the prompt gets `verify`'s verdict (`check_holds`) as a fact; the model's `reply_moves_forward` is dropped for such a
  reply, so the level does not change, right or wrong (the developer's decision).
- `hint.md`: follow the verdict; if false, do not state the correct value.

Out of scope: a line with a variable in a reply (for example `-2x + 6`) still gets a full diagnosis. Routing of replies (Layer 5)
is unchanged. No eval run (evals are debt); checked by the developer re-sending the chat.
