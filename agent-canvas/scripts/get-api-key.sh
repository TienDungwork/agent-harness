#!/usr/bin/env bash
# Print the local Creanova agent-server API key (X-Session-API-Key).
set -euo pipefail

KEY_FILE="${OH_SESSION_API_KEY_PATH:-${OH_CANVAS_SAFE_STATE_DIR:-$HOME/.creanova/agent-canvas}/api-key.txt}"

# Fallbacks from earlier renames / OpenHands layout
if [[ ! -f "$KEY_FILE" ]]; then
  for candidate in \
    "$HOME/.creanova/agent-canvas/api-key.txt" \
    "$HOME/.Creanova/agent-canvas/api-key.txt" \
    "$HOME/.openhands/agent-canvas/api-key.txt"
  do
    if [[ -f "$candidate" ]]; then
      KEY_FILE="$candidate"
      break
    fi
  done
fi

if [[ ! -f "$KEY_FILE" ]]; then
  echo "API key file not found." >&2
  echo "Start the stack once (npm run dev / docker compose up), then retry." >&2
  echo "Expected: $HOME/.creanova/agent-canvas/api-key.txt" >&2
  exit 1
fi

cat "$KEY_FILE"
echo
