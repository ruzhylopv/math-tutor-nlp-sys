# Plan: pre-fetch the review for address-review (approved 2026-10-25)

Problem (first CI run, PR #7): the agent could not read the inline comment because the
`Bash(gh api repos/:*)` allow rule did not match, so nothing was changed. Loosening the rule would
re-open the `gh api` write hole, and the skill picked the "latest" qualifying review without
checking its author (review of PR #6, P2).

Change:
1. The workflow fetches only the triggering review (by id) and its inline comments with its own
   read-only `gh api` calls, fails if the review author is not `ruzhylopv`, and writes them to
   `.review-context/` (git-ignored).
2. The skill reads those files in CI and never calls `gh api`; the local path stays as before but
   is restricted to one review's comments.
3. The agent's allowlist drops `gh api`; `Bash(gh api:*)` is explicitly denied.
4. Stale wording fixed (CLAUDE.md, skill header); the skill notes `/address-review` matching is
   case-insensitive and that text after it is part of the request.

Files: `.github/workflows/address-review.yml`, `.claude/skills/address-review/SKILL.md`,
`CLAUDE.md`, `.gitignore`, `docs/decisions.md`.

Test: push a commit to PR #7 (refreshes its merge ref), then submit a Comment review with the body
`/address-review`; the inline "Add a nice Shakespeare quote" comment should be applied.
