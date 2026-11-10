# Plan: hints from a stale diagnosis, and a plainer "balance" counterexample (approved by delegation, 2026-11-10)

The developer reported a hint that made no sense and delegated the plan and the fix ("fix it all yourself").

## What happened
Problem `3^x - 1 = 4`. The student first wrote `3^x - 1 + 1 = 5 + 1`, `3^x = 6` (wrong) and got a level-1 hint. Then they
sent corrected lines, `3^x - 1 + 1 = 4 + 1`, `3^x = 5`, together with "Still idk what to do next". The tutor answered: "With
x = 2, the left side minus the right side is 4 in the line before and 3 in your line."

At x = 2, left minus right is 4 for the problem and 3 only for the **old** wrong line, so the hint was about a mistake that had
already been fixed. The new lines are correct.

Cause, in `orchestrator._new_message`:
1. The message had steps and a question, so its intent was not `answer`, and the model chose the route.
2. The model chose `hint`. Code allows `hint` whenever an `error_context` exists, so the new lines never went to `verify`.
3. The level rose to 2, and `hint` built a counterexample from the stored `error_context`, which still held the old wrong line.

This breaks the CLAUDE.md rule that every submitted step goes through SymPy.

## Layer 1: `fix/stale-diagnosis-hint` (orchestrator)
- **Rule:** when the model picks `hint` and an old diagnosis exists, new working that `verify` can check goes to `diagnose`
  instead. Working that `verify` can check means at least one line that parses and has a variable (so neither a plain
  calculation nor a prose line such as "I added 1 to both sides"), and no letter that is not in the problem.
- **Level:** in `diagnosed`, a clarifying question (intent `explain`) after a hint keeps the level, as it does on the
  `hint` route.
- **Kept as they are:** plain calculations (`is_calculation_reply` keeps the earlier diagnosis for them) and lines with a new
  letter (`verify` does not know definitions from an earlier turn). Both keep going to `hint`, as today.
- **Scope:** only the model's `hint` is overruled. `ask` and `reply` with working stay as they are, because existing tests pin
  them on purpose (for example `test_the_override_leaves_a_message_with_working_alone`).
- **Tests:** the reported case with a scripted model, a plain calculation, a line with a new letter, a reason-only line,
  and a clarifying question with the same misconception keeping the level.

## Layer 2: `fix/balance-counterexample-wording` (hint, through `tools/counterexample`)
- **Problem:** a "balance" counterexample (both sides of the equation changed) is described as "the left side minus the right
  side is 4 in the line before and 3 in the student's line". That is abstract, and the student cannot check it from what they
  see.
- **Change:** the counterexample also keeps what each side of each line becomes (SymPy computes them), and `describe()` says it
  as "the line before becomes `8 = 4`, where the left side is 4 more than the right side; the student's line becomes `9 = 6`,
  where the left side is 3 more". The "side" and "expression" kinds are unchanged.
- **Prompt:** level 2 in `hint.md` tells the model to quote what each line becomes, so the student can check it, and to ask about
  how far apart the sides are in plain words, not "left side minus right side".
- **Tests:** the new description, a negative gap, a gap of zero, and the existing `side` description staying the same.

## Out of scope and debt
- No eval run. The hint and orchestrator evals need real model calls, which need the developer's yes on a call budget first. This
  is recorded as eval debt in docs/crisp_dm_log.md.
- No new dependency. No change to eval datasets, labels or existing tests.
