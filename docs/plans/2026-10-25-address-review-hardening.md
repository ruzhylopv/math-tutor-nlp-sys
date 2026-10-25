# Plan: address-review hardening (approved 2026-10-25)

Fixes the findings of the PR #12 review (P1: the allowlist file was agent-writable; P2: silent partial
posting, fail-fast loop, float ids, agent-controlled text) and the tool-list loopholes from the PR #9
review (broad `uv run`, `gh pr view`/`gh pr diff`, weak push rules, writable `.claude/`, `.github/`,
`CLAUDE.md`).

## Files
`.github/workflows/address-review.yml`, `.claude/skills/address-review/SKILL.md`,
`docs/decisions.md`, this plan.

## Test result (stubbed `gh`, throwaway git repo, `bash -eo pipefail`)
- good entries posted; a non-object element, a numeric `commit`, a float id, a duplicate id, an id
  outside the review, a string id and a bad status were skipped without aborting the rest;
- a fake sha was dropped, a real one kept;
- `@`, `#12`, `![` and `](` were neutralised;
- a failing post produced a warning, the remaining reply was still posted, and the step exited 1;
- a non-array file failed loudly; an empty list and a missing file were no-ops.
Not yet run on a real runner: do it on a fresh throwaway PR after merging.

- dedupe after validation (a bad entry no longer hides a good duplicate); junk entries no longer use up the 50-reply cap.

## Added after the first CI run of per-thread replies (PR #13 smoke test)
The Claude step used 13 turns (cap 10), was reported as failed, and the post step was skipped, so no
thread replies appeared. Fixes: `--max-turns 20`; the post step runs when the agent step fails; the
skill writes `replies.json` before pushing and commenting; dedupe now runs after validation;
`.git/**` added to the Edit/Write denies.

## Out of scope
Branch protection on `main` (only the owner can enable it). Pagination beyond 100 comments.
