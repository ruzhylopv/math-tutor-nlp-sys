# Plan: the chat input during a turn (approved by delegation, 2026-11-08)

The developer delegated the plan and its decisions to the agent. UI only, `app.py` and `ui.py`; no eval.

## Changes
- A message sent during a turn reruns the script and aborts the graph. `st.chat_input(submit_mode="disable")` (Streamlit 1.66)
  turns the input off on submit and back on when the run ends.
- `st.write` joins single newlines. `ui.hard_line_breaks` keeps them, for user messages only: live, from history and after a
  failed turn. Shift+Enter already adds a newline in the input; the placeholder now says so.
- `on_submit` clears `trace` and `step_log`, so the previous turn's log goes as soon as a message is sent. It runs before the
  script, so the panel never redraws the old log.

## Out of scope
- `*` and `_` in a student's message are still read as Markdown (`2*x*3` turns italic).
- The sidebar buttons stay enabled during a turn: `submit_mode` keeps no state in Python, so disabling them needs a new flag.
