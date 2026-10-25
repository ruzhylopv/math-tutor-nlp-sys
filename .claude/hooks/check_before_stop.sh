#!/usr/bin/env bash
# Before the agent finishes: if Python files changed, require types and tests to pass.
input=$(cat)

# Avoid an infinite loop if the agent is already continuing because of this hook.
[[ $(echo "$input" | jq -r '.stop_hook_active') == "true" ]] && exit 0

changed=$(git status --porcelain -- '*.py')
[[ -z "$changed" ]] && exit 0

if ! out=$(uv run mypy 2>&1); then
  printf 'Type check failed, fix before finishing:\n%s\n' "$(echo "$out" | tail -30)" >&2
  exit 2
fi

out=$(uv run pytest -q -x 2>&1); code=$?
# Exit code 5 means "no tests collected", which is fine early in the project.
if [[ $code -ne 0 && $code -ne 5 ]]; then
  printf 'Tests failing, fix before finishing:\n%s\n' "$(echo "$out" | tail -30)" >&2
  exit 2
fi
exit 0