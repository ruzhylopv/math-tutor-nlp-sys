#!/usr/bin/env bash
# After every edit: format the Python file and report lint errors back to the agent.
file=$(jq -r '.tool_input.file_path // empty')
[[ "$file" == *.py ]] || exit 0

uv run ruff format "$file" >/dev/null 2>&1
if ! out=$(uv run ruff check --fix "$file" 2>&1); then
  printf 'Lint errors in %s, fix them:\n%s\n' "$file" "$out" >&2
  exit 2
fi
exit 0