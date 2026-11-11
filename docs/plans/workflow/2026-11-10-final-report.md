# Plan: final report (approved 2026-11-10)

The homework report, in the course template (https://github.com/ucu-ai-course/ucu-ai-hw-template, commit
c19c770), copied into `report/`. Must cover every item of the assignment PDF ("NLP. Assignment 1. Build an NLP
System"): task, data, components with a data-flow diagram, the prototype, per-component evaluation, CRISP-DM,
skills and agent-instruction files, and material for the demo video.

## Constraints
- Template rule: only `report/report.md` and `report/images/` may change. The rest of `report/` is a byte-identical
  copy (its Pages workflow only runs when the template is the root of its own repository).
- The renderer is marked + KaTeX: no Mermaid, so diagrams are hand-written SVG files in `report/images/`
  (no new dependencies).
- Every number comes from a committed result file in `evals/results/` or a dataset count; every citation is checked.
- Evaluation scope (developer's decision): free runs only. The deterministic evals (verify, localize, retrieve)
  are run once on the test split; parse_input, orchestrator and hint get no new model calls and are reported as debt.

## Stack (one concern per layer, bottom first)
1. `chore/report-test-split-evals`: the three test-split runs, result files and CRISP-DM entries.
2. `docs/report-scaffold`: the template copied into `report/`, the front matter and the section outline, this plan.
3. `docs/report-problem-data`: business understanding (goal: localize the wrong step and repair a broken
   solution, not general math help; why a graph instead of one prompt), related work, data understanding and
   preparation (what is taken as-is, mined, generated, hand-written; sizes, splits, caveats).
4. `docs/report-architecture`: architecture diagram, components (purpose, input, output, model and tool calls),
   a walkthrough of one input, the development plan (milestones, flexible input, polishing) with a timeline.
5. `docs/report-evaluation`: metric choice, results per component (dev and test), charts, analysis of low scores,
   debt.
6. `docs/report-agentic-dev`: CLAUDE.md, skills, subagents, hooks, permissions, the review/fix loop, stacks, the
   `/address-review` GitHub workflow; how to run; demo-video outline; limitations; requirement checklist.

Each layer: one review pass (fix P0/P1 only), PRs stay drafts for the developer's detailed review.
