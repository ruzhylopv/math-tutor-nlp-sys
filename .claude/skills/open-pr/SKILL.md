---
name: open-pr
description: Push the current work and open a pull request, or a stack of PRs, using the project template. Use when a feature, fix or chore is finished and committed, or when the user asks to open, submit or push a PR.
---

# Open a PR

Every change reaches `main` through a PR. The developer reviews and merges; you never merge.

## Step 1: Check the branch
1. `git branch --show-current`. If it is `main`, stop: create a branch first
   (`git switch -c feat/<topic>`, or `gh stack init <branch>` for a stack). Move any uncommitted or
   committed work onto it before continuing.
2. `git status`. Commit anything pending with a conventional message. Do not leave work uncommitted.

## Step 2: Decide single PR or stack
Look at `git diff --stat main...HEAD`. Use a stack when the work has more than one logical concern
or is about 400+ changed lines. Typical layers: state and models, node and prompt, tests and eval,
graph wiring, docs. Dependencies go in lower layers.
- Stack: follow the `gh-stack` skill. Read `references/stack-design.md` before splitting. Create the
  layers with `gh stack init` / `gh stack add`, one concern per branch.
- Single PR: continue below.

## Step 3: Checks
Run `uv run ruff check . && uv run mypy && uv run pytest -q` on every branch you are about to
push. pytest exit code 5 (no tests collected) is fine early in the project. Fix failures first.

## Step 4: Push and open
- Single PR: `git push -u origin <branch>`, then
  `gh pr create --base main --title "<conventional title>" --body-file <file>` where the body follows
  `.github/pull_request_template.md`, every section filled in (write "N/A" or "None", never leave the
  placeholder comments).
- Stack: `gh stack submit --auto` (always `--auto`, a bare `submit` prompts). Then edit each PR body to
  follow the template with `gh pr edit <n> --body-file <file>`, including its stack position.
- Never push `main`, never force-push, never merge. Branches stay as drafts unless the user asks for
  `--open`.

## Step 5: Review loop
Run the `review-loop` skill on the PR (one review, in parallel for every layer of a stack; a fix round only for P0/P1).

## Step 6: Report
Give the user the PR URL(s), the stack order, check results, and anything the review loop escalated.
