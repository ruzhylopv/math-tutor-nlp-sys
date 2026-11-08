# Plan: a live graph panel with a node log (approved 2026-11-08)

Follows `2026-11-02-m7-step-log.md`. Goal: show the architecture on screen while a turn runs, with the running node in green
and a log of what each node did. Two PR layers on top of #88, which also changes `send_stream`.

## Layer 1: trace data (`feat/trace-events`)
- `src/tutor/trace.py`, pure and without Streamlit: `Trace` (runs, active, failed, finished), `graph_dot` (DOT text from
  `get_graph(xray=True)`, so a new node appears by itself; the inner `diagnosis:__end__` is collapsed), `node_path` and
  `node_details` (a whitelist of one-line summaries per node).
- `ui.StepStarted` and `ui.StepFinished` gain `path`, and `StepFinished` gains `details` and `failed`, excluded from
  equality, so the existing event tests stay unchanged.
- `TutorState.decision_reason`: the orchestrator keeps `Decision.reason` for the log instead of discarding it.

## Layer 2: panel (`feat/graph-panel`)
- `layout="wide"`; the panel is a keyed `st.container` placed on the right with CSS, and falls below the chat on a narrow
  screen. Drawn with `st.graphviz_chart` (rendered in the browser, no new dependency).
- Running node green, `diagnosis` with a green border while a step inside it runs; nodes and edges used this turn tinted,
  a failed node red, repeat runs `×2`. Only the latest turn is kept, in `session_state`, not in the checkpoint.

## Who sees what (decided with the developer)
- Everyone: the graph, node names and timings.
- "Developer view" toggle (replaces "Show visited nodes"): verdicts, the misconception, the routing reason. Showing these
  by default would tell the student what a level-1 hint wants them to find.
- Nobody: `hint_text`. It can hold a draft the leak check later rejects, so it may contain the answer.

## Out of scope
- LaTeX rendering. The in-chat step log expander stays for now.
- No eval: UI only, as for the step log.

## To confirm in a browser first (layer 2)
That the graph redraws without flicker and that the CSS also moves the pinned chat input. If it flickers, the fallback is a
small HTML component holding our own SVG (`st.html` strips SVG).
