# Plan: address-review (event-driven, approved 2026-10-25)

Goal: when the developer submits "Request changes" on a PR, Claude Code runs in GitHub Actions and
fixes the requested changes on that PR's branch.

## Decisions (from the developer)
- GitHub Actions on `pull_request_review: submitted` (event-driven).
- Auth: Claude Pro OAuth token (`CLAUDE_CODE_OAUTH_TOKEN` repo secret); Claude GitHub app installed.
- Triggers only for review author `ruzhylopv`, `changes_requested`, same-repo PRs (the repo is public).
- `--max-turns 10`.
- Lands as the top layer of the PR stack.
- Stacks: CI fixes only the reviewed PR's branch. Layers above are rebased locally
  (`gh stack rebase --upstack`, `gh stack push`).

## Files
- `.github/workflows/address-review.yml`
- `.claude/skills/address-review/SKILL.md`
- `CLAUDE.md` (short rule), `docs/decisions.md` (decision and rejected alternatives)

## Unverified until first run (test on a throwaway PR)
- Whether the action pushes to the PR branch rather than a `claude/...` branch.
- The `permissions:` scopes needed on the OAuth path.
- Whether `actions/checkout` before the action is compatible with the action's own checkout handling.
- Subscription usage limits and terms for CI use.
