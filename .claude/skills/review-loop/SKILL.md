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
1. **Review once, in parallel.** For each PR (each layer of a stack), create a detached worktree of its
   branch outside the repo (`git worktree add --detach <scratch>/rev-<n> <branch>`) and spawn the
   `code-reviewer` subagent in the background with that path and the base branch. Reviewers read the
   worktree only; none of them checks out a branch in the shared checkout. Wait for all reports.
2. **Fix only blockers.** If a report has a P0 or P1, spawn the `review-fixer` subagent for that layer
   (a worktree with the branch checked out), with the P0/P1 lines only. One commit. P2, P3 and the
   over-engineering signs are never fixed here. If there is no P0 or P1, nothing is fixed.
3. Re-run `uv run ruff check . && uv run mypy && uv run pytest -q` yourself on a layer that was fixed,
   confirm the fixer's commit exists, then `gh stack rebase --upstack` and `gh stack push` (or `git push`).
4. **Stop.** There is no second review pass and no final re-review. A fix that fails the checks is
   escalated, not retried in a loop.

## Escalate
A P0 or P1 the fixer declined or could not fix safely, and any finding that would need an eval dataset,
expected label or existing-test edit, goes into the PR comment under "Needs a human decision". Never
work around a declined finding yourself.

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
