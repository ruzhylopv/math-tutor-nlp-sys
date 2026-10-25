#!/usr/bin/env bash
# Before a Bash command: refuse git commit/push while on main, so work always goes through a branch.
cmd=$(jq -r '.tool_input.command // empty')
[[ "$cmd" =~ git[[:space:]]+(commit|push) ]] || exit 0

branch=$(git branch --show-current 2>/dev/null)
if [[ "$branch" == "main" ]]; then
  echo "On main: create a feature branch first (feat/<topic>, or gh stack init <branch>). See CLAUDE.md." >&2
  exit 2
fi
exit 0
