# Plan: a clickable graph panel in the style of a GitHub Actions run (approved by delegation, 2026-11-08)

The developer delegated this plan and its decisions ("do the work yourselves without my input"). Follows
`2026-11-08-graph-panel.md`, and overrides its "who sees what" section: the Developer view toggle goes.

## Goal
Status icons per node (spinning amber ring while running, green check, red cross, muted circle when not reached), durations,
connector lines and repeat counts. Clicking a node shows its runs and what each run decided. The log scrolls.

## Spike findings (Streamlit 1.66, Chromium through Playwright, scripted fake turns, no model calls)
| Way of redrawing `st.components.v2.component` in one script run | Result |
|---|---|
| Same `key` each time | `StreamlitDuplicateElementKey`, the run dies |
| No key, or a new key each time, in `st.empty` | Works, but 30 remounts in 30 redraws and blank frames (2-4 of about 400) |
| One keyed mount, plus a hidden unkeyed component that passes each update through `window` | 1 mount, 29 updates, 0 blank frames in 400 |

- A click handled in the browser never reruns the script (script runs stayed at 2 through the click), which matters because a
  rerun would kill the running turn. The selection and the spin animation survive because the DOM is never replaced.
- An unkeyed update needs a different payload each time or it raises a duplicate id, and two states can be equal (a node finishes,
  then the turn ends with an error), so every update carries a monotonic stamp.
- Root cause of "you cannot scroll logs": the pinned chat bar (`stBottom`, z-index 99) spans the whole window width, so it lies
  over the bottom of the fixed panel. A wheel there does nothing (`scrollTop` stayed 0 at y=560 of 620, and moved at y=420), and
  the last log line stopped at y=604 behind the bar, which starts at y=490. Fix: the panel goes above the bar.

## Layer 1: view model (`feat/panel-view-model`)
`trace.panel_view(graph, trace, steps)`: pure and JSON-serialisable, derived from `get_graph(xray=True)` so a new node appears by
itself. Nodes (rank, slot, status, count, seconds, runs with details), edges (conditional, back, taken), groups, with the inner
end joined through. Details still come only from the `node_details` whitelist, so `hint_text` cannot reach the panel.

## Layer 2: component (`feat/graph-component`)
- `src/tutor/panel/`: `panel.js`, `panel.css`, `update.js` as real files, and a small Python module that registers them.
- The SVG is built once per graph shape, then only classes and text change. Model text goes in with `textContent`.
- The panel sits above the chat bar. The log stays native below the graph (`st.text` per step, `st.code` for what it decided).
- Remove the Developer view toggle: details are always shown.

## Who sees what (changed by the developer)
Everyone sees the graph, timings and what each node decided, including verdicts and the misconception. Nobody sees `hint_text`.

## Out of scope
- Deleting `graph_dot`: it becomes unused, but `tests/test_trace.py` asserts it, and tests are only changed with the developer's
  say-so. Flagged in the PR.
- No new dependency. No eval: UI only.
