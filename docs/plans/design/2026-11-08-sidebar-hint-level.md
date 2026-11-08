# Plan: sidebar hint counters at normal size, with the cap (approved by delegation, 2026-11-08)

The developer delegated the plan approval for the UI refinement work. Part of that work; one independent PR.

## Problem
`st.metric` draws "none yet" and the hints count far larger than the rest of the sidebar, and nothing says how high the
hint level can go.

## Change
- `app.py` `show_sidebar`: "Hint level" and "Hints used" become plain `st.markdown` lines, the size of the name line above.
  The level reads `2 / 4`, or `none yet (max 4)` before a hint.
- `src/tutor/ui.py`: `SidebarInfo.max_hint_level`, from `canned_hints.MAX_LEVEL`, so the number has one source.

## Out of scope
- The "Developer view" toggle: its removal is in the graph panel stack, which rewrites the code it controls.
- No eval and no model calls: UI only.
