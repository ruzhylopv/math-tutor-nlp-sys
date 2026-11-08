# Plan: remove classify and finish_diagnosis (approved 2026-11-08)

Layer 6 of `docs/plans/design/2026-11-02-flexible-input.md`. Evals are debt for layers 4-6. Stacked on #82.

- `classify` removed: node, prompt, `eval_classify.py`, its tests and the `Classification` model. `parse_input` writes
  topic and level. `classify.jsonl` and its builder stay, because the parse_input topic eval uses that dataset.
- `finish_diagnosis` removed. The design said an edge condition replaces it, but the node did real work, so that work
  moves: the orchestrator sets `stage` when it routes to `diagnose`, and builds `error_context` in `_diagnosed` with a
  helper in `tools/diagnosis.py`. A clean solution ends the subgraph after verify; anything else ends after retrieve.
- App labels for both nodes removed.
- Tests that name these nodes are updated or removed; only those references change.
- The orchestrator's reset on `topic` None now needs the key to be present: it relied on `classify` refilling the topic.
