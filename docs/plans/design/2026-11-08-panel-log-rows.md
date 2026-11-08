# Plan: the panel's node card and fold-out log rows (approved in chat, 2026-11-08)

Follows `2026-11-08-graph-panel-v2.md`. The developer chose the look from a throwaway mock.

## Goal
From top to bottom: the graph, a card when a node is selected, a plain separator, then one fold-out row per finished step, appended
one after another. No collapsible around the log. The card answers a different question from the rows: with five orchestrator runs,
the card lists only those, and the rows list the whole turn.

## Behaviour
- A click on a node shows its card under the graph. A click on the same node hides it. With nothing selected there is no card.
- A click on a node never opens or closes a row. A row folds out on its own click.
- A step with no details has nothing to fold out, so it has no chevron. A row appears when its step finishes, as the log does today.

## Changes (`feat/panel-log-rows`, stacked on #95)
1. `trace.panel_view` gains `log`: the finished steps in order (`node`, `label`, `seconds`, `failed`, `details`). Details still come
   only from the `node_details` whitelist, so `hint_text` cannot reach the page.
2. `panel.js` and `panel.css` draw the card and the rows.
3. Rows are only appended, so an open row stays open while a turn runs. The list is rebuilt only for a different turn. Which rows
   are open is kept beside the selection, so it survives the graph being rebuilt.
4. `app.py` loses `draw_log` and the log slot: Streamlit no longer draws the log.

## Tests (changed with the developer's say-so)
`tests/test_app.py` read the log through `app.text` and `app.code`, which no longer exist. The `_panel_text` helper and
`test_what_a_node_decided_is_always_in_the_log` now read the data sent to the panel. The assertions stay the same.

## Out of scope
No new dependency. No eval and no model calls: UI only, checked in Chromium on a scripted stream.
