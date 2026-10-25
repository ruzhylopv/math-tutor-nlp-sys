# Plan: per-thread replies for address-review (approved 2026-10-25)

Goal: answer each inline review comment in its own thread instead of one summary comment.

## Decisions (from the developer)
- Replies appear as `github-actions[bot]` (posted by a workflow step with `GITHUB_TOKEN`).
- Replies inside existing threads are not answered; the developer submits another review if needed.
- Threads are not resolved by the bot.

## Design
- The agent still has no `gh api`. It writes `.review-context/replies.json`
  (`{comment_id, status: done|not_done, text, commit}` per comment).
- A workflow step posts each reply with `POST /repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`
  (the endpoint takes a `body` and a top-level comment id; replies to replies are not supported).
  It accepts only ids found in `comments.json`, a valid status, at most 50 replies, 1000 characters
  per text, a commit that looks like a sha, and defuses `@` mentions.
- `comments.json` now carries each comment's `id` and only top-level comments.
- One short summary comment remains (checks, anything not done).

## Files
`.github/workflows/address-review.yml`, `.claude/skills/address-review/SKILL.md`,
`docs/decisions.md`, this plan.

## Not in this PR
Tightening the agent's tool list (review findings from PR #9): separate PR.

## Test
Submit a `/address-review` comment review with two inline comments on a fresh throwaway PR; expect two
thread replies plus one summary comment. The posting script was also exercised locally with a stubbed `gh`.
