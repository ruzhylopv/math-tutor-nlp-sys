---
name: review-loop
description: Review an open PR with a reviewer subagent and fix findings with a fixer subagent, at most 2 passes, then post the result on the PR. Use right after open-pr, or when asked to review or clean up a PR or stack layer.
---

# Review loop

You (the main agent) run the loop. Subagents cannot spawn subagents, so do not delegate the loop itself.
For a stack, run it once per layer, bottom to top, and push each fixed layer before moving up
(`gh stack rebase --upstack` after fixing a lower layer, then `gh stack push`).

## Inputs
- The PR number and branch. The base is `main`, or the parent branch for a stack layer.

## Each pass (maximum 2)
1. Check out the layer's branch.
2. Spawn the `code-reviewer` subagent with the base branch. Ask for findings in its P0-P3 format.
3. If there are no P0, P1 or P2 findings, stop. The PR is clean.
4. Otherwise spawn the `review-fixer` subagent with the full findings text. P3 is left alone.
5. Re-run `uv run ruff check . && uv run mypy src && uv run pytest -q` yourself and confirm the fixer's commits exist.
6. Push the branch (`git push`, or `gh stack push` for a stack).

After pass 2, run the reviewer once more without fixing, to get the final state.

## Escalate, do not loop forever
Anything still P0 or P1 after pass 2, anything the fixer declined, and any finding that would need an
eval dataset or existing-test edit goes into the PR comment under "Needs a human decision". Never
work around a declined finding yourself.

## Post the result
Post one comment with `gh pr comment <n> --body-file <file>`, and fill the PR body's "Review loop"
section (`gh pr edit`):
- passes run;
- findings per tier: found, fixed, remaining;
- remaining P3 nits, listed;
- "Needs a human decision" items, if any;
- the final check results.

## Report to the user
The PR URL, the tier counts, and what needs their decision. Do not merge.
