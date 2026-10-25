# Plan: PR-based agent workflow (approved 2026-10-25)

Goal: agents work on branches and open PRs (stacked when the work has several concerns); a
reviewer subagent and a fixer subagent run a bounded review loop on each PR. The developer only
reviews PRs and merges.

## Decisions (from the developer)
- Agents may push feature branches. `main` is protected by deny rules and a hook.
- The plan gate stays: plans are approved in chat first.
- Stacked PRs via `gh stack` (installed, stacked PRs enabled on the repo).
- `add-node.md` and `run-eval.md` move to `<name>/SKILL.md`.
- Review loop: at most 2 passes.

## Severity tiers
- P0 blocker: secrets/.env access, edits to test datasets or labels, broken build, failing
  tests or types, destructive command.
- P1 critical: violation of a hard CLAUDE.md rule (LLM does math, inline prompt, node contract,
  eval examples copied into a prompt) or wrong behaviour.
- P2 should fix: weak or missing tests, over-engineering, missing docs/log entries.
- P3 nit: style and naming. Reported in the PR comment, never auto-fixed.

## Stack
1. `chore/pr-workflow-rules`: this plan, CLAUDE.md rules, settings.json permissions,
   `block_main.sh` hook, docs/decisions.md.
2. `feat/pr-template-and-open-pr`: `.github/pull_request_template.md`, `open-pr` skill, existing
   skills moved to `<name>/SKILL.md` with the final step handing off to `open-pr`.
3. `feat/review-loop`: `review-loop` skill, rewritten `code-reviewer` (PR diffs, P0-P3),
   new `review-fixer` agent.

## Notes
- Subagents cannot spawn subagents, so the main agent orchestrates the loop via the skill.
- Layer 1 was opened by hand because the workflow did not exist yet.
