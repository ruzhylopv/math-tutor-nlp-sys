# Plan: chat history and hints before any working (approved 2026-11-08)

A student with a stored problem who says they cannot start was asked for their working on every turn. `hint` needs a
diagnosis and a diagnosis needs steps, so that student had no route to help, and the nodes saw only the last tutor message.

Scope limit: the tutor coaches a student into a specific problem; it does not teach algebra in general.

| Situation | Tutor does |
|---|---|
| Problem given, student cannot start or asks how the method applies | Asks one guiding question |
| General question with no problem | Asks for a specific problem |
| Student asks for a lesson or the method's steps | Still asks a guiding question, no walkthrough |
| Student submits working | Unchanged: SymPy checks it |

Three stacked PRs:

1. **Chat history** (`feat/chat-history`). A helper in `tools/messages.py` formats the last 20 messages before the latest
   student message. `orchestrator` and `hint` get it as `Conversation so far`; the existing lines stay. `parse_input` keeps
   only the last tutor message, so old equations are not taken for new steps.
2. **Hints before working** (`feat/hint-before-working`). `hint` is allowed with no diagnosis when a problem is stored and
   the student is stuck, asks how to start, or replies to one of these hints. The orchestrator prompt keeps `ask` for bare
   answers and stops repeating it to a student who said they cannot start. `hint` gets a "no working yet" situation: one
   question about the idea, no judgement of the student's math. The first such hint is level 1. A leak falls back to a canned
   text written for this case. An out-of-scope subject is declined instead of coached.
3. **`parse_input` remarks** (`fix/parse-input-remarks`). A remark about the student's own situation is not a step. Any new
   example is written from scratch, not taken from the eval datasets.

Evals: dev-split runs for the changed nodes where a dev dataset exists. The routing dev set has no labelled file; about 10
"stuck with no working" cases are picked with the developer once the code is in. If an existing test has to change, stop
and ask first.

Known limit: the leakage check reads backticked math and bare `x = 2`, not prose like "the roots are 2 and 3". A prompt
rule covers it for now.
