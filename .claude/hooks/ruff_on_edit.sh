#!/usr/bin/env bash
# PostToolUse (Edit|Write): formatea y corrige con ruff el .py editado dentro de backend/.
# Si quedan errores no autocorregibles, los devuelve a Claude (exit 2) para que los arregle.
set -u
file=$(jq -r '.tool_input.file_path // empty')
case "$file" in
  "$CLAUDE_PROJECT_DIR"/backend/*.py) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0
cd "$CLAUDE_PROJECT_DIR/backend" || exit 0
uv run --quiet ruff format "$file" >/dev/null 2>&1
out=$(uv run --quiet ruff check --fix --output-format concise "$file" 2>&1)
if [ $? -ne 0 ]; then
  echo "ruff: quedan errores en $file" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
