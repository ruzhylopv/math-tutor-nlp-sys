# Decisions log

Format: date | decision | alternative rejected | why.

## 2026-10-25 | PR-based workflow driven by agents
- **Decision:** agents work on feature branches, push them, and open PRs (stacked via `gh stack`
  for multi-concern work). The developer only reviews and merges.
  - Rejected: agents commit to `main`. No review point, nothing for the developer to check.
- **Decision:** the review loop runs locally in a skill (reviewer subagent, then fixer subagent).
  - Rejected: a GitHub Actions review. Needs API keys and CI setup; harder to iterate on.
  - Rejected: a Stop-hook-driven loop. Hard to bound and to tell apart from normal stops.
- **Decision:** the main agent orchestrates the loop. Subagents cannot spawn subagents.
- **Decision:** agents never merge; `gh pr merge` and `gh stack merge` are denied.
  - Rejected: agent self-merge after a clean review. Removes the human check the assignment wants.
- **Decision:** the loop is capped at 2 passes; unresolved P0/P1 findings are escalated in the PR.
  - Rejected: loop until clean. Can churn indefinitely on subjective findings.
- **Decision:** keep the plan-approval gate before multi-file changes.
  - Rejected: moving the plan into the PR description. Code would be written before approval.

## 2026-10-25 | address-review runs in GitHub Actions
- **Decision:** a `pull_request_review` workflow runs Claude Code when the developer requests
  changes, using the Pro OAuth token, restricted to `ruzhylopv`, `--max-turns 10`.
  - Rejected: polling with `/loop`. Only works while a local session is open; delayed.
  - Rejected: a scheduled cloud routine. Still polling, extra setup.
- **Decision:** CI fixes only the reviewed branch; stack rebases happen locally.
  - Rejected: installing `gh-stack` in the workflow. More setup and more failure modes for a rare case.
- **Decision:** replies are one summary PR comment, and `gh api` is limited to GET-style calls.
  - Rejected: per-thread replies via `gh api` POST. Needs write-capable `gh api`, which could also merge.

## 2026-10-25 | address-review also triggers on a `/address-review` comment review
- **Decision:** a "Comment" review by the developer whose body starts with `/address-review` also
  triggers the workflow, because authors cannot request changes on their own PRs.
  - Rejected: a second GitHub account for reviews. Needs an account and a changed login check on a public repo.
  - Rejected: bot-authored PRs from a second Actions workflow. Larger change; unverified who the author would be.
  - Rejected: triggering on every comment review. Fires on routine inline comments; the phrase makes it explicit.
