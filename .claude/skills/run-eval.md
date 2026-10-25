---
name: run-eval
description: Run the evaluation for one tutor component, save metrics, compare with the previous run, and log the result. Use when the user asks to evaluate, benchmark, test quality or check metrics of a component.
---

# Run an evaluation

## Inputs
- Component name (e.g. `verify`, `retrieve`, `routing`). If not given, ask.
- Split: `dev` by default. Use `test` ONLY if the user explicitly asks for final numbers.
  If they did not, do not run on test.

## Step 1: Pre-checks
1. Confirm `evals/scripts/eval_<component>.py` and the dataset file for the split exist.
   If either is missing, stop and say what is missing. Do not create labels yourself.
2. Run `git status`. If there are uncommitted changes in `src/`, tell the user the result will not
   match a commit, and ask whether to commit first or continue.

## Step 2: Run
`uv run python evals/scripts/eval_<component>.py --split <split>`
If it crashes, report the error and stop. Do not change the dataset, labels or metric code to make it
run. Fixing the eval script itself is allowed only if the user agrees.

## Step 3: Result file
Confirm a new file exists at `evals/results/<component>/<timestamp>_<git-hash>.json` containing:
split, number of examples, every metric, model name, and prompt file hash if it is an LLM node.

## Step 4: Compare
Find the previous result file for the same component and split.
- Make a table: metric | previous | current | change.
- Mark any metric that dropped by more than 2 percentage points (or 2% relative for non-percentages)
  as a REGRESSION.
- If there is no previous result, say this is the baseline.

## Step 5: Error analysis
Show 3 to 5 failed examples from the run's output: input (shortened), expected, predicted.
Group the failures into rough categories if a pattern is visible (e.g. "parse errors on fractions").
Do not suggest changes based on test-split failures; only dev-split failures may guide iteration.

## Step 6: Log
Append an entry to `docs/crisp_dm_log.md` under **Evaluation**:
`YYYY-MM-DD | <component> | <split> | <key metric>=<value> (change) | <git-hash> | one-line note`

## Step 7: Report to the user
The comparison table, any regressions, the failure categories, and one suggested next step.
Do not modify code or prompts in this skill. Iteration is a separate task.