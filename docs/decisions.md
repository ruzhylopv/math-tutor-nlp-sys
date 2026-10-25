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
- **Target level (provisional): MATH Algebra, levels 1-3** | all MATH subjects | keeps scope small.

## OPEN items (not decided)
- What the orchestrator does when the leakage check rejects a hint (regenerate with a cap, canned
  fallback, or loop back to `hint`).
- Whether `localize` writes a `focus_step` for `omission_extraneous_root`, where `first_error_step` is None.
- How the learner profile is keyed across sessions (the checkpointer uses `thread_id`; a `student_id` is needed).
- How Eedi's multiple-choice records map to the retrieval query (problem + wrong step); verify its
  fields and Kaggle terms before use.
- The target grades, and the final free OpenRouter model.

## OPEN: error-type taxonomy and its data (added after the PR #11 review)
Status: not decided. The four error types come from the planning handoff and have not been checked
against real student work. Published sources exist (see `docs/architecture.md`, section
"Error-type taxonomy: candidate sources").
- **Derive the taxonomy from data**, not from the handoff alone: map labels from the candidate
  datasets onto ours and count what does not fit. Decide after that mapping.
- **Add a fallback value** (`other` / `unclassified`) so unmatched cases are visible. Undecided.
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
