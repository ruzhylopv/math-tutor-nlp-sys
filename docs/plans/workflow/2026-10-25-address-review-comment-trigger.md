# Plan: comment-review trigger for address-review (approved 2026-10-25)

Problem: GitHub does not let a PR author approve or request changes on their own PR, and agent PRs
are opened with the developer's account. The "Request changes" trigger cannot fire for them.

Change: the workflow also fires for a "Comment" review by `ruzhylopv` whose body starts with
`/address-review`. "Request changes" keeps working (for PRs authored by someone else).

Files: `.github/workflows/address-review.yml`, `.claude/skills/address-review/SKILL.md`,
`docs/decisions.md`.

Test after merge: on a throwaway PR add an inline comment, submit the review as "Comment" with the
body `/address-review`, and watch the Actions tab.
