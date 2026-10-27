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
  (Superseded 2026-10-25: `gh api` was removed from the agent in CI; see the pre-fetch and thread-reply entries.)
  - Rejected: per-thread replies via `gh api` POST. Needs write-capable `gh api`, which could also merge.

## 2026-10-25 | address-review also triggers on a `/address-review` comment review
- **Decision:** a "Comment" review by the developer whose body starts with `/address-review` also
  triggers the workflow, because authors cannot request changes on their own PRs.
  - Rejected: a second GitHub account for reviews. Needs an account and a changed login check on a public repo.
  - Rejected: bot-authored PRs from a second Actions workflow. Larger change; unverified who the author would be.
  - Rejected: triggering on every comment review. Fires on routine inline comments; the phrase makes it explicit.

## 2026-10-25 | address-review pre-fetches the review; the agent has no `gh api`
- **Decision:** a workflow step fetches the triggering review and its inline comments (GET, by review
  id, author checked) into `.review-context/`; the agent reads those files only.
  - Rejected: fixing the allow pattern (`gh api repos/*`). Still lets the agent read other users'
    comments and, with flag gaps (`--field`, `--input`), reach write endpoints.
  - Rejected: a deny-list of `gh api` write flags. Easy to miss one; an absent capability cannot be misused.
  - Note: on a public repo the login check on the trigger is the only guard on who can start a run,
    and the pre-fetch now also ties the instructions to that same review and author.

## 2026-10-25 | Tutor design (from the planning handoff)
Format: decision | rejected alternative | why.
- **Topic:** misconception-diagnosing math tutor | answer-giving math chatbot; contract red-flag
  assistant; paper-review assistant | personal fit, public labelled data per stage, clear demo.
- **Hybrid:** fixed pipeline plus agentic orchestrator | fully agentic flow | per-stage evaluation
  needs fixed, inspectable stages.
- **LangGraph for orchestration, plain functions for nodes** | classic LangChain chains; a
  hand-written loop | explicit state, conditional edges, checkpointer, graph export; chains add
  hard-to-debug layers.
- **SymPy for all math checking** | LLM verification | LLMs make arithmetic errors.
- **Equivalence vs implication in `verify`** | equivalence-only check | squaring is valid but not
  reversible; avoids blaming correct steps.
- **Retrieval over a misconception catalogue** | RAG over textbooks | answers "why is this wrong" and
  has labelled eval data.
- **Diagnosis as a separately compiled subgraph** | nodes inline in the main graph | evals can call it
  without the chat layer.
- **Hint returns to the orchestrator, not straight to the student** | hint replies directly | central
  leakage check and hint-level control.
- **Skip diagnosis when the student asks a question** | always re-run diagnosis | same result, wasted
  calls.
- **Streamlit UI** | custom web frontend | enough for the demo.

## 2026-10-25 | Choices made while turning the handoff into docs
- **LLM provider: OpenRouter with a free model** | Anthropic API via `langchain-anthropic` (already a
  dependency) | the developer does not want to pay for tokens. Consequence: likely `langchain-openai`
  with a `base_url` replacing `langchain-anthropic`; the change needs approval and goes in the first
  LLM node's plan. Free models vary in structured-output support; to be checked then.
- **Retrieval: in-memory sentence-transformers + FAISS** | a LangChain vector store; a vector DB server
  | fewer layers than a server or a framework store. The catalogue size is UNVERIFIED (earlier text
  said "a few hundred"; that had no source). New dependencies need approval.
- **`localize`: rules on SymPy verdicts first, LLM only to interpret and check justifications** |
  LLM-first localization | keeps the "LLM never checks algebra" rule.
- **Leakage check: a deterministic function in `src/tutor/tools/`, called by the orchestrator** | logic
  inside the orchestrator node | testable without the graph and reusable in the hint eval.
- **Learner DB: SQLite with `attempts` and `misconceptions_seen`** | a document store; no persistence |
  small, relational, no server.
- **Target level (provisional): MATH Algebra, levels 1-3** | all MATH subjects | keeps scope small. Superseded 2026-10-26, see M3 decisions.

## OPEN items (not decided)
- (Resolved 2026-10-25: retry once, then a canned fallback; see "Design gaps" below.)
- (Resolved 2026-10-25: `localize` writes `focus_step`; `student_id` is a name from a login-style UI field. See "State additions" below.)
- How Eedi's multiple-choice records map to the retrieval query (problem + wrong step); verify its
  fields and Kaggle terms before use.
- The target grades (resolved 2026-10-26), and the final free OpenRouter model.

## OPEN: error-type taxonomy and its data (added after the PR #11 review)
Status: partly decided (the fallback value is resolved, the rest is not). The four error types come from the planning handoff and have not been checked
against real student work. Published sources exist (see `docs/architecture.md`, section
"Error-type taxonomy: candidate sources").
- **Derive the taxonomy from data**, not from the handoff alone: map labels from the candidate
  datasets onto ours and count what does not fit. Decide after that mapping.
- **Add a fallback value** (`other` / `unclassified`) so unmatched cases are visible. (Resolved 2026-10-27, see
  M4a decisions: `other` was added. It now covers unparsable steps and steps that stop early (incomplete answers),
  and, in the current rules, a lost solution through a `narrows` step. The other cases below stay open.)
- **Cases the four types do not cover:**
  - lost solutions (for example dividing by `x` loses `x = 0`), the opposite of `omission_extraneous_root`;
  - several errors in one solution (`first_error_step` names only the first);
  - a correct final answer reached through invalid steps (the graph currently short-circuits on `is_correct`);
  - a wrong method choice, or answering a different question;
  - copy errors (misreading the problem makes step 1 `not_valid`, labelled `algebraic_transformation`);
  - unparsable steps (`StepVerdict` can be `unparsable`, but no error type or route exists);
  - steps that stop before an answer (not `final_answer_only`).
- **`final_answer_only` has no producer.** Proposed: `classify` finds zero steps and the orchestrator
  routes to `ask`, so `localize` never emits it. Undecided.
- **Eedi catalogue size and coverage are unverified.** The number of distinct misconceptions is
  unknown, and the misconceptions expected by scenarios A and B may not exist in it. Fallback: a
  small hand-made supplement.

## 2026-10-25 | address-review replies in each thread, posted by the workflow
- **Decision:** the agent writes `replies.json`; a workflow step validates and posts one reply per
  top-level inline comment as `github-actions[bot]`. Replies inside existing threads are ignored.
  - Rejected: the agent posting replies with `gh api`. Needs a write-capable `gh api`, which we removed
    from the agent on purpose (it could reach merge and other endpoints).
  - Rejected: a single summary comment only (the earlier choice). The developer wants each comment answered.
  - Rejected: the bot resolving threads. Left to the developer.
  - Accepted trade-off: replies show as `github-actions[bot]`, not the `claude` identity of the summary comment.

## 2026-10-25 | address-review hardening (from the PR #9 and PR #12 reviews)
- **Decision:** the post step re-fetches the allowed comment ids itself instead of reading
  `comments.json` after the agent ran, runs with `pipefail`, skips malformed entries, dedupes by id,
  warns and continues when one post fails (then fails the job), verifies the commit with
  `git cat-file`, and neutralises `@`, `#<digits>`, `![` and `](` in the agent's text.
  - Rejected: keeping the allowlist file somewhere the agent "should not" write. Not a boundary.
  - Rejected: stopping at the first failed post. Silently drops the other replies.
- **Decision:** narrower agent tools: only `uv run pytest|ruff|mypy`; no `gh pr view`/`gh pr diff`;
  `git push` only plain or `origin HEAD`, with pushes to `main`, `--delete`, `+refspec` and
  force variants denied; `Edit`/`Write` tools denied on `.claude/**`, `.github/**`, `.git/**` and `CLAUDE.md`.
  - Rejected: `Bash(uv run:*)`. Allows arbitrary code through `uv run python`.
  - Consequence: a review that asks the agent to change those protected paths gets `not_done`.
- **Residual risks (accepted, not removed):**
  - `uv run pytest` runs repository code, so a malicious test file could run commands, and
    `GITHUB_TOKEN` is in the job environment. The trigger is limited to the developer's reviews on
    same-repo PRs.
  - The path protection covers the Edit and Write tools only: `uv run pytest` can write any file and
    `git diff`/`git log` accept `--output`. `.github` is backstopped because `GITHUB_TOKEN` cannot push
    workflow changes; `.claude` and `CLAUDE.md` are not.
  - Reply text is only partly neutralised (bare URLs, `GH-12`, HTML and reference-style links still
    render). The summary comment (`gh pr comment`) is not neutralised at all.
  - A workflow re-run after a partial failure can post some replies twice.
  - Branch protection on `main` is the real backstop; only the repository owner can enable it.

- **Decision (after the first run of per-thread replies):** `--max-turns` raised from 10 to 20, and the
  post step runs with `if: ${{ !cancelled() }}`. The smoke test used 13 turns; the action reported
  failure ("exceeding the configured maximum of 10") and skipped the post step although the work was
  done. The skill now writes `replies.json` before pushing and commenting, and checks the branch with
  `git status` (a denied `git branch` call had wasted a turn).
  - Rejected: keeping 10 turns. The task needs more than that.
  - Rejected: no cap. A cap bounds the Pro usage of a run.

## 2026-10-25 | Design gaps found in the PR #11 review
Format: decision | rejected alternative | why.
- **`verify` short-circuits only when the answer is correct, every step is valid and no justification is
  flagged** | redefining `is_correct` as "answer right and nothing flagged" | one field would hide two facts.
  Fixes required behaviour 5 and the "right answer through invalid steps" case.
- **`diagnosis` and `hint` always return to the orchestrator; the orchestrator has three modes (new message,
  after diagnosis, after hint)** | `diagnosis -> hint` directly, or the leakage check inside `hint` with its own
  retry loop | the hint level can only be reset or escalated by the orchestrator, and the central leakage check
  was the original reason for routing hints back. The two non-LLM modes are plain code, so no extra LLM call.
- **Leakage failure: retry `hint` once, then a canned hint for the level** | looping until the hint passes |
  a hard cap keeps the loop bounded.
- **Hint level resets when a different misconception id is diagnosed and escalates by one for the same id;
  levels 1-4, capped at 4; practice offered at the third occurrence** | (provisional numbers) | simple and
  testable. The cap and the threshold may change after the first scenario runs.
- **Numbers in hints (counterexamples) come from a SymPy tool, never from the LLM** | letting the hint LLM
  pick the values | breaks the "LLM never does arithmetic" rule.
- **`hint` writes `hint_text`; only the orchestrator and UI write `messages`; one `reply_text` field** |
  `hint` writing straight to `messages` | a rejected hint would already be in the chat history.
- **`final_answer_only` is produced by `classify` and routed to `ask`, not by `localize`** | keeping it as a
  `localize` output | `localize` is never reached in that case.
- **Step numbers are 1-based; step 1's predecessor is the problem statement.**

### Still OPEN after this change
- The counterexample tool: how it chooses a value, its interface, when `hint` calls it. (The rule is decided.)
- The checkpointer: in-memory for now; a persistent one is a new dependency and needs approval.
- The error-type taxonomy and Eedi items above;
  the hint cap, the recurrence threshold, the target grades (resolved 2026-10-26) and the final model.

### Found in the design-gaps review (not decided; to settle before the nodes they touch)
- **`stage` writers: settled** (see "finish_diagnosis" below). The UI and the scenario runner must still set
  `new_message` at the start of every run.
- **Reset points** for `hint_retries`, `turns`, `hints_used`, `misconceptions_seen` and `hint_level` when a hint
  is published, a new problem starts or `record_attempt` has run, and for the diagnosis fields (`misconception`,
  `error_type`, `first_error_step`, `misconception_candidates`) that go stale when `verify` short-circuits.
  `finish_diagnosis` could clear the stale ones; undecided.
- **`final_answer_only` path.** `classify` writes no routing field and the subgraph has no early exit on zero
  steps. Either the orchestrator `Decision` is the only path to `ask`, or add an edge after `classify`.
- **Leakage-check inputs.** The check needs the correct final answer and the key intermediate expression; no
  state field holds them. Recompute from `problem` with SymPy, or add a reference-solution field written by `verify`.
- **What "valid" means in `verify`**: (Resolved 2026-10-26: equivalent, implies, or narrows to the original problem's
  solution set; unparsable is not valid. Scenario B T4 is the `narrows` case; see "M2 data decisions" below.)
- **Non-arithmetic wrong justifications** give `justification_claims_ok = None`, so `verify` short-circuits and
  behaviour 5 holds only for justifications SymPy can check, until the `justification_claim` extraction is settled.
- **`misconceptions_seen` entries** hold ids only, but `record_attempt` stores `error_type` and `focus_step` too.
- **Reads columns** in the node table: `localize` also needs `is_correct`; `hint` needs `error_type` and `is_correct`.
- **Precedence** when both `omission_extraneous_root` and `reasoning_result_mismatch` hold (the mismatch
  variant of scenario B).
- **Single predicate** for "correct and nothing flagged": one pure function in `tools/`, used by both `verify`
  and the orchestrator.

## 2026-10-25 | `finish_diagnosis`: a tiny last node in the diagnosis subgraph
- **Decision:** the diagnosis subgraph ends in a deterministic node `finish_diagnosis` that writes
  `stage = diagnosed`. Both exits (`verify`'s short-circuit and `retrieve`) go through it. The subgraph itself
  is a node of the main graph, but it writes no fields of its own, so a node inside it must write `stage`.
  - Rejected: splitting the orchestrator into `route`, `after_diagnosis` and `after_hint`. It would remove the
    `stage` field and make each mode a separate file, but adds two nodes and replaces the approved single
    orchestrator.
  - Rejected: a wrapper node in the main graph that calls the compiled subgraph. It hides the subgraph's inner
    steps from graph export and streaming.
  - Rejected: `verify` and `retrieve` each writing `stage`. Two writers for one fact.
- **OPEN:** CLAUDE.md requires an eval script for every node. `finish_diagnosis` has nothing to measure. Either
  a unit test only (needs an exemption in CLAUDE.md, the developer's call) or a trivial eval stub.

## 2026-10-25 | State additions settled
- **`localize` writes `focus_step`** | reusing `first_error_step = None` | `retrieve` and `hint` need a step to talk
  about for `omission_extraneous_root`.
- **A separate LLM node, `parse_input`, extracts the problem and structures the student's text into the state.
  Input is text only for now** | an optional `problem_text` on the orchestrator's `Decision`; a vision/OCR model
  now | the orchestrator should route, not extract; a vision model is out of scope.
- **`justification_claim` is an optional field on `Step`**, filled where the steps are split and evaluated by SymPy
  in `verify` | having the LLM judge justifications | the LLM never checks math.
- **`student_id` is a name typed into a login-style field in the Streamlit UI** | real authentication; a random id |
  enough for a demo; a typo creates a new profile, which is acceptable here.
- **`parse_input` takes the problem and the step structure; `classify` only tags topic and level** | one node doing
  both | each node then has its own eval (extraction and step-split accuracy vs topic accuracy).
- **Resolved 2026-10-26:** `parse_input` runs before the orchestrator (alternative rejected: first node of the
  diagnosis subgraph, to save a call on pure questions). See "M3 decisions" below.
- **Consequence:** CLAUDE.md requires an eval script per node; `parse_input` gets one (problem-extraction and
  step-split accuracy).

## 2026-10-25 | M1 decisions
- **Replace `langchain-anthropic` with `langchain-openai` for OpenRouter** | keeping the Anthropic client | the
  developer will use a free OpenRouter model and does not want to pay for tokens. Base URL and structured-output
  support are verified (docs plus `scripts/check_llm.py`) before relying on them.
- **API key variable `OPENROUTER_API_KEY`** | keeping `LLM_API_KEY` | names the actual provider; `.env.example` updated.
- **`finish_diagnosis` is exempt from the per-node eval-script rule** (one line in CLAUDE.md) | a trivial eval stub |
  it is a deterministic marker with nothing to measure; unit tests still apply.
- **LLM client in `src/tutor/llm.py`; shared eval runner in `evals/runner.py`.**

## 2026-10-25 | M1 implementation notes (all six layers; recorded here to keep the stack mergeable)
- **The "correct and nothing flagged" predicate (`is_clean_solution` in `tools/diagnosis.py`) was written in M1,
  not M2**, because the diagnosis subgraph's conditional edge needs it. How substitute / check steps count as
  valid is still settled in M2.
- **`evals` is packaged with the project (`packages = ["src/tutor", "evals"]` in `pyproject.toml`)** so
  `uv run python evals/scripts/eval_x.py` can `import evals.runner` from any folder | a `sys.path.insert` plus
  `# noqa: E402` in every script (tried first, then removed); running scripts with `-m` (changes the allow rule in
  `.claude/settings.json` and the `run-eval` skill) | one packaging line instead of a repeated hack, and the
  documented command is unchanged.
- **Node stub tests share one parametrised file (`tests/test_node_stubs.py`)** | one file per node | the stubs are
  identical in shape; each real node gets its own test file when its logic lands.
- **`ruff` treats `evals` as first-party (`src = [..., "."]`) and pytest puts the repo root on `pythonpath`.**
- **`docs/graph.mmd` is generated by `scripts/draw_graph.py` and committed** for the report; regenerate it when the
  graph changes.
- **State (layer 2):** `LearnerProfile` is a small pydantic model (weak topics, misconception counts) even though the
  outline did not list it | typing `learner_profile` as `dict[str, Any]` | a typed shape is easier to test; its
  fields come from the learner-DB draft and are finalised in M6. `level` is a plain `int`; `hint_level` is an `int`
  noted as 1-4 in a comment | a `Literal[1, 2, 3, 4]` alias | no node needs the narrower type yet.
- **Config (layer 3):** the API key is excluded from `Config`'s repr (`field(repr=False)`) and the LLM client holds it as
  a `SecretStr`, so logs and tracebacks cannot print it. An empty value in `.env` counts as missing.
- **`check_llm.py`:** tries each structured-output method three times, asks for JSON in the prompt so `json_mode` is a
  fair test, prints usable and flaky methods and exits non-zero if none works every time. `temperature=0` is hard-coded
  in `llm.py`; some reasoning models reject it, so check on the chosen model.
- **Eval runner (layer 4):** the layout `evals/datasets/<split>/<component>.jsonl` is our convention (CLAUDE.md fixes
  only `dev/` and `test/`). The runner moved ahead of the stubs because every eval stub uses it. `git_hash` runs in the
  evals folder and falls back to `"nogit"` so a finished eval never loses its metrics. The `.gitignore` rule for
  `evals/results/*.json` matched nothing and is removed: result files are committed, as the `run-eval` skill expects.
  `mypy` checks `evals/` through `files = ["src", "evals"]` in `pyproject.toml`. An explicit `mypy src` overrides
  that setting, so (with the developer's approval) CLAUDE.md, the stop hook, the agents, the skills and the PR
  template now run plain `uv run mypy`.
- **Eval stubs (layer 5):** each stub is a docstring and one call to the shared `run_eval_stub`; tests redirect the
  datasets folder to a temp dir so they do not depend on real datasets.
- **Routing default:** `route_from_orchestrator` ends the run when `next_action` is missing (the state is `total=False`).
  Revisit when the real orchestrator exists; raising on an unknown action may be better.
- **`docs/graph.mmd` escapes:** langgraph writes `\3a` for the `:` in subgraph node ids. Not yet verified to render in
  Mermaid; if it does not, post-process the file in `scripts/draw_graph.py`.
- **Open for later milestones:** `Classification.topic` is free text; M3 decides whether it becomes a `Literal` or a
  catalogue-backed set. A visited-nodes test on the main graph needs `stream(..., subgraphs=True)`, because the default
  updates stream shows top-level nodes only.

## 2026-10-26 | M2 data decisions
- **Task types: solve, simplify, expand and factor** | solve-for-x only | the cleanest MATH chains are simplify and
  expand tasks, and all four fit the tutor's scope.
- **Positives are mined from MATH solutions** | writing them all by hand | realistic formatting, and the labels come
  from the human solution authors, so they are independent of SymPy. Costs a LaTeX-to-plain-text converter.
- **Wrong steps are produced by the agent, labelled by rule, with provenance, a numeric guard and a developer
  spot-check** | hand-written by the developer; labels from SymPy (circular) | an explicit exception to the
  `run-eval` skill's "do not create labels yourself", approved by the developer.
- **SymPy only; no LLM-only variant or ablation** | an LLM-only localization comparison | the project's claim is that
  verification is enforced by the system, and the extra variant is not wanted.
- **Linear chains only; a solution with sub-computations is split into separate chains** | branching support | much
  simpler. Known limitation: a student's sub-computations can give a false `not_valid` on the line that does not
  follow the previous one.
- **A new relation `narrows`**, valid only when the result equals the original problem's solution set | reusing
  `equivalent` or `implies` | rejecting an extraneous root shrinks the solution set, which is neither.
- **Final-answer data from PRM800K**, with candidate labels from its grader, our SymPy check run alongside, and the
  developer adjudicating the disagreements | labels from SymPy alone (circular) | independent labels at low cost.
- **PRM800K's -1 rating is not used as a `not_valid` label.** It means "everything else" (inaccurate, weird,
  off-topic or not checkable in 30 seconds), not "algebraically invalid" | using -1 as ground truth | it would label
  valid-but-odd steps as errors. 0 and +1 ("no inaccuracies") may serve as extra valid-step evidence.
- **PRM800K and MATH are MIT-licensed repositories.** PRM800K states no separate data licence. Raw files stay outside
  the repo; only small derived datasets are committed.

## 2026-10-26 | M2 implementation notes
- **Mined pairs are identity lines only**: no complex numbers, uppercase names, function notation or custom
  operations, and both lines must use the same variables. Conditions and substitutions (`xy = 6`, "= 0") hold only
  under a hypothesis and would mislabel as `equivalent`. Cost: a legitimate simplification to a number is skipped.
- **The checker parses decimals exactly and rejects `1.2.3`**; both bugs were found by the mined data and the
  hand-written cases, not by the hand-built unit tests.
- **`evals/builders/`, not `evals/build/`**: `.gitignore` ignores `build/`, which silently dropped the first commit.
- **Hand-written cases are split stratified by relation, not by problem** | by problem | they share problem texts, so
  a split by problem left the rare relations nearly empty in test.
- **Mined positives are filtered by the checker's agreement** | keeping the disagreements as hard cases | the
  disagreements are author typos and condition-dependent lines, not checker faults; they go to a review file and the
  agreement rate is reported separately. Consequence: accuracy on the splits is high by construction.
- **The node is evaluated through its real interface**: a case runs as `problem = original or prev` and the last step
  is `curr`, so `narrows` is recognised and closed check lines behave as in use.
- **`verify` needs a plain-text problem statement** (parse_input's job, M3); a prose problem makes step 1 `unparsable`
  (conservative: never praise an unchecked step). Rejecting a root with `not equal` (`3 != -3`) is not parsed.
- **`is_correct` for an expression task is equivalence to the problem expression**; a partly simplified answer still
  counts as correct because the node does not know the task type.

## 2026-10-26 | M2 review fixes (stack of fix/ branches after PRs #29-#33 had merged)
The five reviews found five P1s; the stack had been merged before they could be fixed, so the fixes are new PRs.
- **Any SymPy failure, and a 5 second wall-clock guard, mean "unparsable"** | letting exceptions escape; a worker
  process with a timeout | SymPy raises many exception types and can hang on small inputs. The guard uses SIGALRM, so it
  works in the main thread on Unix only; elsewhere there is no guard (revisit for the Streamlit app, M7).
- **Input limits before SymPy evaluates**: 200 characters, no stacked powers (`9^9^9`; `2^(3^2)` is lost too), exponents up
  to 1000 on a number or a single variable and 50 on a bracketed base | a timeout alone | the interrupt cannot stop a huge
  integer power quickly. Python number syntax (`3e+2`, `0x10`) and non-real values are rejected.
- **Variables are real** | complex symbols | the plan says reals; `sqrt(x^2)` must equal `abs(x)`.
- **Nested `abs` is not handled** | trusting `solveset` | it returns a wrong set for `abs(abs(x)-1) = 2`. Each root
  `solveset` returns is also substituted back.
- **Decimals are parsed as exact rationals** | a float tolerance; `nsimplify` | tolerance would make 0.1+0.2 vs 0.31
  depend on a threshold.
- **`+-` and `±` expand into two equations joined by "or"** | reading `+-` as `+(-x)` (what Python does) | the architecture
  writes scenario B this way; the old reading silently dropped one root.
- **An equation with no solutions followed by any equation is `not_valid`** | `implies` (set logic) | a student who
  "solves" a contradiction must not be told the step is fine. This relabelled the hand-written case
  `x/(x-3) = 3/(x-3)` -> `x = 3` from `implies` to `not_valid`; the case is in the test split, so the change needs the
  developer's review. Other label changes during M2: `x ++ 3` was mislabelled `unparsable` (a unary plus is valid), and the
  sandbox case `__import__('os')` left the dataset (it is a unit test).
- **A check line (a closed statement) has relation `equivalent` and its truth in `StepVerdict.check_holds`** | calling a false
  check `not_valid` | the check that rejects an extraneous root (scenario B turn 4) is correct work. Risk: a wrong arithmetic
  claim written as a check line is not flagged by `verify`; `localize` (M4) must read `check_holds`.
- **The answer check says `unparsable` for leftover letters against a numeric truth, treats `1,000` as ambiguous, and compares
  the variable name when both sides give one.** `check_answer` changed on purpose: the test expecting `("x", "9")` to be
  `incorrect` now expects `unparsable`. "No solution" and "all reals" answers are not recognised (limit).
- **The step rule and the answer rule differ on purpose**: a bare `3` answers `x + 1 = 4` but is not a valid step after it.
- **Miner**: `$$..$$`, `\\[2mm]`, multi-column lines, equation pairs with different variables or no variables, uppercase names and
  complex numbers in equation chains, and the `task_type` default (`other`, not `simplify`) were fixed; two unrelated equations
  that share a solution can still be paired (rare, documented). **Converter**: `\cdots` and `\rightarrow` were being cut to
  `\cdot` and `\right`; `1\,000` and characters the checker cannot read (`|`, `,`, `<`, `_`) are dropped.
- **Datasets**: identical pairs across problems are kept once, the unparsable pairs get their own review file, a seeded 20%
  sample of the generated negatives is written for the developer, and the report records the SymPy version. **The committed dev
  and test files are NOT rebuilt yet**: the test split is written by a script, which the `Edit`/`Write` deny does not cover, and
  the developer has not approved it. Rejected alternative: editing the files by hand. After approval the datasets are frozen.
- **The 100% dev accuracy was an artifact**: dev accuracy fell to 0.9975 once the checker changed, and the eval result file now
  carries a note saying so.
- **`verify` needs a plain-text problem statement**; a prose problem makes step 1 `unparsable` and `is_correct` False until M3's
  `parse_input` supplies one (listed in the roadmap). `is_correct` cannot say "could not judge" (a tri-state is an option).

## 2026-10-26 | M3 decisions
- **`parse_input` sits in the main graph between the UI and the orchestrator** | the first node of the diagnosis subgraph
  (proposed earlier) | the orchestrator then routes on a structure (problem, steps) and not only on raw text. Cost: one
  LLM call per message, including pure questions. `parse_input` resets `student_steps` for a message without working, so
  stale steps are never mistaken for a new attempt.
- **OPEN (settle in M5, before `hint` and the orchestrator are built): the `student_steps` reset conflicts with the
  hint path.** `hint` reads the wrong step; `focus_step` and `first_error_step` index into `student_steps` and
  `step_verdicts` is written against them. A question after a diagnosis (scenario B T2, required behaviour 2) is routed
  to `hint` with no new diagnosis; after the reset `hint` has no step to talk about and the indices point at nothing.
  The `diagnose` -> `is_clean_solution` path on a message without steps sees verdicts for steps that no longer exist,
  and the same reset happens when the model fails twice. Options: (a) at diagnosis time store the wrong step's claim
  in a field `parse_input` does not reset, and `hint` reads that; (b) the reset also clears `first_error_step`,
  `focus_step`, `step_verdicts`, `error_type` and `misconception`, and `hint` does not depend on them after a question;
  (c) `parse_input` resets only when the message contains a new attempt (steps found), or when no diagnosis is
  outstanding. Proposal, awaiting the developer: (a), because `hint` keeps what it needs without making the reset
  depend on diagnosis state. Rejected for now: changing the approved reset before the developer has chosen.
- **OPEN (settle with the item above): stale `topic` and `level`.** `classify` returns `{}` on failure or an empty
  problem, so `topic` and `level` keep the value from an earlier problem in the same thread. The orchestrator (or
  `parse_input` when `problem` changes) must clear them.
- **OPEN (settle with the items above; a consumer question for the orchestrator): out-of-scope subjects.** `classify`
  runs inside the diagnosis subgraph, after the orchestrator has already routed to `diagnose`, so it cannot guard
  the scope by itself. Nothing yet says what happens when it returns Geometry, Number Theory, Precalculus or Counting &
  Probability.
- **`topic` is one of the 7 MATH subjects and `level` is MATH's 1-5** | our own finer taxonomy (brackets, quadratics, ...) |
  labels exist, are human-assigned and independent of our code; a finer taxonomy would need hand labels. In scope:
  Prealgebra, Algebra, Intermediate Algebra. `classify` tags the subject; what happens on an out-of-scope subject is not
  designed yet.
- **`parse_input` is evaluated by normalized exact match of each claim** | equivalence under SymPy | SymPy's parser
  distributes `3(x+2)` into `3x+6`, so an LLM that "repairs" a student's mistake would go unnoticed.
- **An invalid model output twice in a row gives an empty result, not an exception** | raising | the orchestrator then asks
  the student to resend; a free model failing once must not crash a session.
- **The committed `verify` datasets are not rebuilt** | rebuilding with the stricter miner (preview: dev 1,237, test 479) |
  the developer decided it was not needed. Known consequence: 12 identical (prev, curr, relation) pairs appear in both
  splits (some non-trivial, so reported test numbers inherit the leakage), and the miner in `evals/builders/` no longer reproduces the committed files.

## 2026-10-26 | M3 implementation notes
- **`classify` returns no update when the model fails twice** (topic and level stay unset) | the "out-of-scope default" the
  plan proposed | a default label would be indistinguishable from a real answer in the state and in the eval; the failure is
  logged and counted in `failure_rate`. The orchestrator must treat a missing `topic` as "not classified" (wiring layer).
- **LLM calls go through `tools/structured.call_structured`** | each node calling the client | one place for the retry, the
  eval cache and the mock point. Nodes call it as `structured.call_structured` (module attribute), so tests patch one name.
- **`parse_input` data is rendered from known structure** | asking a model to write student messages, or collecting real ones |
  the expected problem and steps are known before the message exists (mined MATH chains, some steps made wrong by
  `corrupt.py`), so labels do not depend on a model or on our checker. Cost: the messages are synthetic and only as messy
  as the renderer (layouts, LaTeX, unicode, spoken math, typos in words, chatty frames); hand-written messages (29) cover
  what the renderer cannot. Real student messages are not tested; reported as a limit with the numbers.
- **One chain per MATH problem, subjects Algebra, Prealgebra, Intermediate Algebra, levels 1-3** | all chains | avoids many
  near-identical messages from one solution. 150 generated messages per split plus the hand-written ones.
- **A message that only gives an answer has no steps** | treating the answer as a one-line attempt | it follows the prompt
  ("A bare answer in a message that states no problem and shows no other working is not a step. A line written after a stated
  problem or after other working is a step, including the last line."); an answer-only message is still read by
  the orchestrator from the raw message. Open: whether `verify` should get the bare answer as a step.
- **Two match rules for claims, both on text**: strict (no spaces, trailing stop) and canonical (also `*` and brackets around
  one token ignored) | SymPy equivalence | see the M3 decisions above. The canonical rule exists because mined text carries
  converter artefacts (`x = (19)`), which a model may reasonably drop.
- **Model for M3 evals: `nvidia/nemotron-3.5-super-vl:free`** (set by the developer in `.env`; recorded in every result file).
- **Datasets for `classify` and `parse_input` are written by the developer's own run of the builders**: the test split is
  protected, and the auto-mode classifier blocks an agent's script that writes it.

- **The eval cache: key = model + prompt + schema + user text, opt-in via `LLM_CACHE_DIR`, evals only** | `functools.lru_cache`
  (does not survive across eval runs) and no cache at all | a long eval on a free, rate-limited model must be restartable.
  Consequence: a stale-but-valid answer stays cached until the directory is deleted.
- **`call_structured` returns None after the retry instead of raising** | raising | it retries only transient and
  invalid-output errors (connection, timeout, 429, 5xx, ValueError, OSError); auth, permission, bad-request and
  programming errors propagate, so a wrong key does not look like N silent failures. `method="json_schema"` and a 60 s
  timeout are fixed because the developer's model passed it 3/3.
- **`classify`: `topic` is a closed Literal of the 7 MATH subjects; `level` is MATH's 1-5, chosen by the model from a scale
  defined in the prompt** | free-text topic; a rubric-free level guess | a closed set can be scored and routed on; the
  rubric makes the level reproducible. The eval also reports within-one, because level labels are noisy. The eval feeds
  LaTeX problem text while in use `classify` receives `parse_input`'s plain text (a known gap, noted in the result file).
- **`classify` returning `{}` on failure leaves a stale `topic` and `level` in a thread** | clearing them in `classify` |
  open, see the OPEN items in "M3 decisions" above.

## 2026-10-27 | M4a decisions (`localize`)
- **Error types: the three we have plus `other`** | keeping three and forcing every case into one of them; a separate
  `unparsable_step` type now | the taxonomy was OPEN (see "OPEN: error-type taxonomy"); a fallback makes the cases
  the three do not cover visible in the eval without committing to a finer split before there is data. Covers
  unparsable steps and steps that stop before an answer. A lost solution turned out to be `not_valid` in `verify`
  (checked on `x^2 = 3x`), so it is an `algebraic_transformation`. Still open: lost solutions as their own type,
  several errors in one solution (only the first is reported), wrong method.
- **`localize` is rules only in v1, no LLM** | an LLM classifying the error type | the verdicts already say where and
  roughly what; a model on this path would add latency and could contradict SymPy. A later iteration may add an LLM
  reading of justifications if the eval shows the rules miss it.
- **An `unparsable` step gives `first_error_step` None and `focus_step` = that step** | blaming the step as
  `algebraic_transformation` | SymPy could not judge it; the tutor can still ask the student to rewrite it.
- **`error_type` is optional in `TutorState` (None when nothing is wrong)** | a sentinel value `none` in `ErrorType` |
  an absent error is not an error type, and the stale-field problem (M3 OPEN items) is easier to see with None.
- **PRM800K step labels are not used in v1** | using them as a second opinion now | its solutions are prose and LaTeX
  that need a conversion to plain-text steps which does not exist, and `-1` does not mean "algebraically invalid".
- **For M4b the developer approved a PyTorch-based embedding stack (sentence-transformers, FAISS) and will download
  Eedi** | TF-IDF/BM25 or plain cosine over the catalogue as the only method | the developer chose embeddings; the
  lighter methods stay available as a first baseline if installation size is a problem. The dependency is added in
  the M4b PR.
