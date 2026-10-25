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
