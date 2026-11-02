# Plan: flexible student input (approved 2026-11-02)

## Problem
Chat `Pavlo|4`: the student wrote a correct but unfinished solution with a substitution
(`A = x + 32x^2 + 2`, `5A = 0`, "5 is not 0", `A = 0`) and asked what to do next. verify marked steps 1-3
`unparsable` (two unknowns; a sentence), localize made step 1 the focus, and hint asked the student to do
step 1 again. In the next turn the student answered the hint ("It has to be equal to zero"); the orchestrator,
which never sees the tutor's last message and has no action for an answer, chose `ask` ("write out your
solution"). Each node followed its rules; the pipeline has no notion of line kinds, definitions,
"correct so far" or what the student asked.

## Direction (agreed in chat 2026-11-02)
Keep the pipeline and its NLP components (parsing, SymPy verification, localization, retrieval, graded hints,
orchestration). Remove nodes that do no NLP. Give the LLM nodes more of the reading; SymPy still decides
right and wrong (CLAUDE.md math rule unchanged).

## Changes, one stack layer each
1. **State** (`state.py`)
   - `Step.kind`: `equation | definition | reason | check | other` (default `equation`, so old checkpoints and
     datasets still load).
   - `ParsedInput.intent`: `check_work | stuck | answer | explain | new_problem | other` (`answer`: the student
     replies to the tutor's last question); `ParsedInput.topic`, `level`
     (from the classify merge).
   - `TutorState.intent`.
   - `ErrorType` gets `incomplete`: every checked line is valid and there is no final answer.
2. **parse_input** (prompt and node), classify merged in
   - Label each line's `kind`; reasons in words are `reason` lines (or the next line's justification, as now).
   - Gets the tutor's last message as an input, so it can recognise `answer`.
   - Return `intent`, `topic`, `level`. `classify` node removed; its eval becomes a part of the parse_input eval
     (topic accuracy / macro-F1 kept as metrics, same dataset).
   - Prompt rules written in general terms; no example copied from the eval sets.
3. **verify** (`tools/algebra.py`, node)
   - A `definition` line (`new symbol = expression`) is recorded and substituted into later lines before
     comparing; its own verdict is `equivalent` with the note "definition" (no new `Relation` value).
   - `reason` and `other` lines are not compared; their verdict is `unparsable` with a note, and they are not the
     predecessor of the next line (same treatment as check lines today).
4. **localize** (node)
   - A `reason` / `other` line is never the focus. An `equation` line SymPy cannot read is still the focus
     (no LLM step in localize).
   - All checked lines valid and no final answer: `error_type = incomplete`, focus on the last valid line.
   - retrieve skips `incomplete` (no misconception to look up); the learner DB records no misconception for it.
5. **hint** (prompt and node)
   - Gets `intent`, the last valid line, the tutor's last message and the student's latest message.
   - With `incomplete` and intent `stuck`, the hint points at the next step from that line.
   - With intent `answer`, the hint model judges the student's reply to its own question and responds to it first
     (decided by the developer 2026-11-02: the LLM judges the reply, also when it contains math; SymPy still
     checks every submitted step). It returns a structured verdict on the reply (`moves_forward`: bool) so the
     orchestrator does not raise the hint level when the reply moves forward. The leak check is unchanged.
6. **graph**: `finish_diagnosis` removed (an edge condition replaces it); `classify` removed from the subgraph.
   App labels updated.

Orchestrator: its prompt gets `intent` and the tutor's last message; `answer` routes to `hint` when a diagnosis
exists. The hint level stays when the hint's verdict is `moves_forward`, and goes up otherwise.
Retrieve: unchanged.

This rule change is recorded in `docs/decisions.md`: the LLM judging a reply to a hint is an exception to the
CLAUDE.md math rule ("the LLM never checks algebra"), which the developer owns; the agent does not edit CLAUDE.md.

## Evals (dev split only; new cases chosen with the developer, none copied into prompts)
- parse_input: new cases for line kinds (substitution, reasons in words, mixed prose and math) and intent;
  metrics: kind accuracy, intent accuracy, plus the existing ones and topic accuracy from classify.
- verify: cases with definitions.
- localize: cases with reason lines and "stopped" solutions. The existing labels where an unreadable reason
  line is the focus would change meaning: the developer decides how to relabel; the agent does not edit them.
- hint: cases with the "stopped" outcome and intent `stuck`; cases of replies to a hint question (right, wrong,
  partly right); metric: reply-verdict accuracy, plus the existing leakage rate.
- orchestrator: routing cases where the student answers the tutor.
- Removed: the classify eval script (metric moves to parse_input); `finish_diagnosis` had none.

## Risks
- parse_input now carries more; a wrong `kind` hides an error (a wrong equation labelled `reason` is never
  checked). Measured first, before the later layers.
- Free model structured output: a larger `ParsedInput` schema may fail more often; checked on the dev set.

## Decisions (the developer delegated them to the agent, 2026-11-02)
1. An `equation` line SymPy cannot read stays the focus | an LLM step in localize | one more LLM call per diagnosis
   while a turn already takes 15-65 s; the reason lines that caused the bug are handled by `kind` instead.
2. New `ErrorType` value `incomplete` | `other` with the focus on the last line | retrieve reads `error_type` and must
   skip a solution with no error; `other` also means "unreadable step", which retrieve does search.
3. A definition is `equivalent` with the note "definition" | a new `Relation` value `defines` | no change to the
   shared `Relation` type, verify's eval or localize's rules.
4. CLAUDE.md names the exception in its math rule (one line, in layer 5) | only a decisions entry | agents and the
   reviewer read CLAUDE.md, so without it the hint change would be flagged as breaking the rule.
5. New dev cases: the agent drafts 10-15 handwritten cases per touched eval, marked
   `"provenance": {"spot_check": "pending"}` like the existing handwritten ones, and they are reviewed in each
   layer's PR. Existing cases and labels are not edited; if an existing localize label conflicts with the new
   rules, the agent stops and reports it.

Each layer is one session (CLAUDE.md: one component per session).
