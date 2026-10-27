---
name: review-loop
description: Review an open PR (or every layer of a stack) once with a reviewer subagent, fix only blocking findings (P0 and P1) with a fixer subagent, and post the full review on the PR. One pass, no second review. Use right after open-pr, or when asked to review a PR or stack layer.
---

# Review loop: one review, one fix round only if something blocks

You (the main agent) run the loop. Subagents cannot spawn subagents, so do not delegate the loop itself.
The point is speed: one review per PR, and a fix round only for findings that really block.

## Inputs
- The PR number(s) and branch(es). The base is `main`, or the parent branch for a stack layer.

## Steps
You create and remove every worktree. Put them under the session scratch folder, never inside the repo.
1. **Review once, in parallel.** For each PR (each layer of a stack), create a detached worktree of its
   branch: `git worktree add --detach <scratch>/rev-<n> <branch>`, and spawn the `code-reviewer`
   subagent in the background with that path and the base branch. Reviewers work in their worktree only;
   none of them checks out a branch in the shared checkout. A reviewer runs the gate there, so run
   `uv sync` in the worktree first if its virtual environment is missing. Wait for all reports.
   Remove the review worktrees afterwards (`git worktree remove --force <path>`).
2. **Decide who handles each blocker.** For each report with a P0 or P1:
   - If it needs a human decision (a missing plan approval, a new dependency or infrastructure, a
     design question), do not run the fixer: it goes straight to "Needs a human decision" and still
     counts as blocking in the verdict.
   - Otherwise spawn the `review-fixer` subagent. Give it the P0/P1 lines only and a worktree with the
     branch checked out, which you create after switching the shared checkout off that branch:
     `git worktree add <scratch>/fix-<n> <branch>`. It commits there and does not push. It returns
     "Fixed" and "Not fixed" lines; read them. Anything under "Not fixed" is escalated.
   If there is no P0 or P1, nothing is fixed. P2, P3 and the over-engineering signs are never fixed here.
3. Remove the fix worktree, then for a layer that was fixed re-run
   `uv run ruff check . && uv run mypy && uv run pytest -q` yourself and confirm the fixer's commit
   exists. Push from the shared checkout: `gh stack rebase --upstack` then `gh stack push` (or `git push`).
   A layer that was not fixed reuses the gate result its reviewer reported; the comment's "check results"
   come from the reviewer for unfixed layers and from your re-run for fixed ones.
4. **Stop.** There is no second review pass and no final re-review. A fix that fails the checks is
   escalated, not retried in a loop.

## Escalate
A P0 or P1 the fixer declined or could not fix safely, one that needed a human decision from the start,
and any finding that would need an eval dataset, expected label or existing-test edit, goes into the PR
comment under "Needs a human decision". Never work around it yourself.

## Post the review (always, even when nothing was fixed)
Post one comment per PR with `gh pr comment <n> --body-file <file>`. It is the review, so it lists the
findings explicitly, not just counts:
- **Fixed** (P0/P1): each finding and the commit that fixed it.
- **Should fix (P2)**: every finding, `file:line | problem | suggested fix`.
- **Nits (P3)**: every finding, one line each.
- **Possible over-engineering signs**: the reviewer's section as written: what is complicated, which
  requirement does not need it, the proposed simplification, and the drawbacks of simplifying.
- **Needs a human decision**: anything escalated, and any design question the review raised.
- The check results (ruff, mypy, pytest) of the final state.

Also fill the PR body's "Review loop" section with the same counts and a pointer to the comment.

## Report to the user
The PR URL(s), the counts per tier, what was fixed, the over-engineering signs worth a decision, and
what needs their decision. Do not merge. The developer decides whether any P2/P3 or simplification is
worth doing (`/address-review`, or ask the agent).
