# Plan: one review pass, a fix round only for blockers (approved 2026-10-27)

Goal: shorten the review loop. The two-pass loop (review, fix, review, fix, final review) took longer than
the work it checked. The developer asked for one review-and-fix loop, a fix only when something really
blocks, and a check for unnecessary complication, since this should be a simple system.

## Decisions (from the developer)
- One review pass per PR; no second pass and no final re-review.
- The fixer runs only for blocking findings (P0 and P1).
- P2 and P3 findings are reported explicitly in the PR comment, as the review.
- The reviewer reports critical simplicity findings under "Possible over-engineering signs", each with a
  clear proposal for how to simplify and the drawbacks of doing so.

## Decisions (agent defaults, for review in the PR)
- **Reviews of a stack run in parallel**, each reviewer in its own detached worktree, never in the shared
  checkout (a reviewer once switched the shared checkout to `main`).
- **Over-engineering signs never block and are never auto-fixed**, except a new dependency or
  infrastructure without an approved plan, which is a P1 and also listed with its simpler alternative.
  Minor generality (an unused optional parameter) is a P3 nit, not a sign.
- **The reviewer's scope is the diff**: run the gate once; no experiments, no dataset rebuilds.
- **A failed fix is escalated**, not retried in a loop.

## Changes
`CLAUDE.md` (the review-loop bullet), `.claude/skills/review-loop/SKILL.md` (the loop),
`.claude/agents/code-reviewer.md` (a required "Possible over-engineering signs" section, severity
tiers, scope), `.claude/agents/review-fixer.md` (P0 and P1 only, one commit),
`.github/pull_request_template.md` and `.claude/skills/open-pr/SKILL.md` (wording).

## Risks
- A P2 that matters can be postponed because nothing forces a fix; the PR comment lists every P2 so the
  developer can decide (`/address-review`, or ask the agent).
- One pass can miss a regression introduced by the fixer; the fixer's commit is checked with the gate.
