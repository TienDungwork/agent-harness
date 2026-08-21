#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# agent-canvas all-in-one entrypoint
#
# Starts three services (plus an optional fourth):
#   1. Agent Server   on port $AGENT_SERVER_PORT  (default 18000)
#   2. Automation     on port $AUTOMATION_PORT     (default 18001)
#   3. Static server  on port $PORT               (default 8000)
#      Routes /api/automation/* → automation, /api/* → agent-server,
#      and serves the frontend static build for everything else.
#   4. (Optional) Public-mode static server on $PUBLIC_MODE_PORT
#      Same frontend, but with --auth-required (no baked session key).
#      Used by auth-mode E2E tests. Only started when PUBLIC_MODE_PORT is set.
#
# Environment variables:
#   PORT                 – Unified entry point port (default: 8000)
#   AGENT_SERVER_PORT    – Internal agent-server port (default: 18000)
#   AUTOMATION_PORT      – Internal automation port (default: 18001)
#   AGENT_CANVAS_BASE_PATH – Static frontend mount path (default: /canvas)
#   PUBLIC_MODE_PORT     – If set, starts a second static server on this port
#                          with --auth-required (no session key injected)
#   OH_SECRET_KEY        – Secret key for settings encryption (auto-generated
#                          and persisted if not provided)
#   Creanova_AUTOMATION_API_KEY – Override automation backend auth key
#                          (defaults to session API key — both backends
#                          use the same `X-Session-API-Key` header)
#   AUTOMATION_AGENT_SERVER_URL  – URL the automation service uses to reach the
#                          agent-server (default: http://127.0.0.1:AGENT_SERVER_PORT).
#                          Setting this enables local-mode auth so the session
#                          API key is validated internally instead of against the
#                          Creanova cloud API.
#   FILE_STORE             – Storage backend for automation tarballs (default: local).
#                          Without this the automation backend may fall back to
#                          S3/GCS which fails without cloud credentials.
#   LOCAL_STORAGE_PATH     – Directory for local file storage (default: ~/.Creanova/storage)
#   AUTOMATION_BASE_URL    – Publicly-reachable base URL for the automation
#                          service, used in callback URLs and injected into
#                          sandboxes (default: http://127.0.0.1:$PORT).
#                          Override in production when the external URL differs.
#   AUTOMATION_WORKSPACE_BASE – Directory for automation run workspaces
#                          (default: ~/.Creanova/workspaces)
#   Any agent-server or automation env vars are passed through.
# ═══════════════════════════════════════════════════════════════════════════════
set -uo pipefail

log() { printf '[agent-canvas] %s\n' "$*"; }
log_error() { printf '[agent-canvas] ERROR: %s\n' "$*" >&2; }

# ── Load centralized defaults (generated from config/defaults.json at build) ─
# shellcheck source=/dev/null
if [ -f /opt/agent-canvas/defaults.env ]; then
  # shellcheck disable=SC1091
  . /opt/agent-canvas/defaults.env
fi

PORT="${PORT:-${CONFIG_PROXY_PORT:-8000}}"
AGENT_SERVER_PORT="${AGENT_SERVER_PORT:-${CONFIG_AGENT_SERVER_PORT:-18000}}"
AUTOMATION_PORT="${AUTOMATION_PORT:-${CONFIG_AUTOMATION_PORT:-18001}}"
AGENT_CANVAS_BASE_PATH="${AGENT_CANVAS_BASE_PATH:-${CONFIG_CANVAS_BASE_PATH:-/canvas}}"

# Persistence paths — keep settings, conversations, bash history under a
# single well-known directory that the VOLUME directive exposes.
# Hub runtime image uses ~/.openhands; a Creanova-built image uses ~/.Creanova.
if [ -d "${HOME}/.openhands" ] || command -v openhands-agent-server >/dev/null 2>&1; then
  STATE_ROOT="${HOME}/.openhands"
else
  STATE_ROOT="${HOME}/.Creanova"
fi
STATE_DIR="${STATE_ROOT}/${CONFIG_STATE_SUBDIR:-agent-canvas}"
export OH_PERSISTENCE_DIR="${OH_PERSISTENCE_DIR:-${STATE_ROOT}}"
export OH_CONVERSATIONS_PATH="${OH_CONVERSATIONS_PATH:-${STATE_ROOT}/${CONFIG_CONVERSATIONS:-agent-canvas/conversations}}"
export OH_BASH_EVENTS_DIR="${OH_BASH_EVENTS_DIR:-${STATE_ROOT}/${CONFIG_BASH_EVENTS:-agent-canvas/bash_events}}"

# OH_SECRET_KEY is required for settings/secrets encryption. Without it the
# agent-server refuses to return encrypted secrets → conversation creation
# fails with a 503.  Auto-generate and persist (just like the session API key)
# so the image never runs with a known default.
SECRET_KEY_FILE="${STATE_DIR}/secret-key.txt"
if [ -z "${OH_SECRET_KEY:-}" ]; then
  if [ -f "$SECRET_KEY_FILE" ]; then
    OH_SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
  else
    OH_SECRET_KEY="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    mkdir -p "$(dirname "$SECRET_KEY_FILE")"
    printf '%s' "$OH_SECRET_KEY" > "$SECRET_KEY_FILE"
    chmod 600 "$SECRET_KEY_FILE"
    log "Generated OH_SECRET_KEY (persisted to $SECRET_KEY_FILE)"
  fi
fi
export OH_SECRET_KEY

# API key — generate one if not provided so the image doesn't run wide-open
# by default. LOCAL_BACKEND_API_KEY is the single user-facing env var.
# Persisted so restarts reuse the same key.
API_KEY_FILE="${STATE_DIR}/api-key.txt"

if [ -z "${LOCAL_BACKEND_API_KEY:-}" ] && [ -z "${OH_SESSION_API_KEYS_0:-}" ]; then
  if [ -f "$API_KEY_FILE" ]; then
    LOCAL_BACKEND_API_KEY="$(cat "$API_KEY_FILE")"
  else
    LOCAL_BACKEND_API_KEY="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    mkdir -p "$(dirname "$API_KEY_FILE")"
    printf '%s' "$LOCAL_BACKEND_API_KEY" > "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
    log "Generated API key (persisted to $API_KEY_FILE)"
  fi
  export OH_SESSION_API_KEYS_0="$LOCAL_BACKEND_API_KEY"
fi

# Shared token so agent harness can call local-gateway infra APIs without a browser cookie.
INFRA_TOKEN_FILE="${STATE_DIR}/infra-agent-token.txt"
if [ -z "${INFRA_AGENT_TOKEN:-}" ]; then
  if [ -f "$INFRA_TOKEN_FILE" ]; then
    INFRA_AGENT_TOKEN="$(cat "$INFRA_TOKEN_FILE")"
  else
    INFRA_AGENT_TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    mkdir -p "$(dirname "$INFRA_TOKEN_FILE")"
    printf '%s' "$INFRA_AGENT_TOKEN" > "$INFRA_TOKEN_FILE"
    chmod 600 "$INFRA_TOKEN_FILE"
    log "Generated INFRA_AGENT_TOKEN (persisted to $INFRA_TOKEN_FILE)"
  fi
else
  mkdir -p "$(dirname "$INFRA_TOKEN_FILE")"
  printf '%s' "$INFRA_AGENT_TOKEN" > "$INFRA_TOKEN_FILE"
  chmod 600 "$INFRA_TOKEN_FILE"
fi
export INFRA_AGENT_TOKEN

# Both backends share the same API key value and the same `X-Session-API-Key`
# header for authentication.  Default Creanova_AUTOMATION_API_KEY to the
# API key so a single credential secures the whole stack.
EFFECTIVE_SESSION_KEY="${OH_SESSION_API_KEYS_0:-${LOCAL_BACKEND_API_KEY:-}}"
if [ -z "$EFFECTIVE_SESSION_KEY" ]; then
  log "ERROR: No session API key available — cannot configure automation auth"
  exit 1
fi
export Creanova_AUTOMATION_API_KEY="${Creanova_AUTOMATION_API_KEY:-${EFFECTIVE_SESSION_KEY}}"
export OPENHANDS_AUTOMATION_API_KEY="${OPENHANDS_AUTOMATION_API_KEY:-${EFFECTIVE_SESSION_KEY}}"
export AUTOMATION_LOCAL_API_KEY="${AUTOMATION_LOCAL_API_KEY:-${EFFECTIVE_SESSION_KEY}}"
export AUTOMATION_AGENT_SERVER_API_KEY="${AUTOMATION_AGENT_SERVER_API_KEY:-${EFFECTIVE_SESSION_KEY}}"
export Creanova_REMOTE_WS_READY_REQUIRED="${Creanova_REMOTE_WS_READY_REQUIRED:-false}"
export OPENHANDS_REMOTE_WS_READY_REQUIRED="${OPENHANDS_REMOTE_WS_READY_REQUIRED:-false}"

# AGENT_SERVER_URL — needed by automation sandbox callbacks.
export AGENT_SERVER_URL="${AGENT_SERVER_URL:-http://127.0.0.1:${AGENT_SERVER_PORT}}"

# AUTOMATION_AGENT_SERVER_URL — the URL the automation service uses to reach
# the agent-server REST API (tarball upload, bash dispatch, auth key minting).
# When set, ServiceSettings.is_local_mode returns True, enabling local API key
# authentication. Without this, the automation server falls back to validating
# keys against the Creanova cloud API (app.all-hands.dev), which returns 401
# for locally-generated session keys.
export AUTOMATION_AGENT_SERVER_URL="${AUTOMATION_AGENT_SERVER_URL:-http://127.0.0.1:${AGENT_SERVER_PORT}}"

# Keep the legacy canvas_ui_tool module importable when the agent-server restores
# conversations whose persisted metadata still references its module qualname.
export OH_EXTRA_PYTHON_PATH="${OH_EXTRA_PYTHON_PATH:-/opt/agent-canvas/tools}"

# Track child PIDs so we can clean up on exit.
PIDS=()

cleanup() {
  log "Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup EXIT SIGINT SIGTERM

# ── 1. Start Agent Server ────────────────────────────────────────────────────
log "Starting agent-server on port $AGENT_SERVER_PORT..."

if command -v Creanova-agent-server >/dev/null 2>&1; then
  Creanova-agent-server --port "$AGENT_SERVER_PORT" &
elif command -v openhands-agent-server >/dev/null 2>&1; then
  openhands-agent-server --port "$AGENT_SERVER_PORT" &
elif [ -x /agent-server/.venv/bin/python ]; then
  if /agent-server/.venv/bin/python -c "import Creanova.agent_server" 2>/dev/null; then
    /agent-server/.venv/bin/python -m Creanova.agent_server --port "$AGENT_SERVER_PORT" &
  else
    /agent-server/.venv/bin/python -m openhands.agent_server --port "$AGENT_SERVER_PORT" &
  fi
else
  log_error "Cannot find agent-server binary or source venv."
  exit 1
fi
PIDS+=($!)

# ── 2. Start Automation Server ───────────────────────────────────────────────
log "Starting automation server on port $AUTOMATION_PORT..."

# Disable the automation's own frontend — agent-canvas provides the UI.
export AUTOMATION_FRONTEND_DIR=""

# File storage — use local filesystem unless the user has configured cloud
# storage.  Without FILE_STORE=local the automation backend may fall back
# to a cloud provider (S3/GCS) which will fail without credentials, causing
# tarball-based presets (preset/prompt, preset/plugin) to silently error.
export FILE_STORE="${FILE_STORE:-local}"
export LOCAL_STORAGE_PATH="${LOCAL_STORAGE_PATH:-${STATE_ROOT}/storage}"
mkdir -p "$LOCAL_STORAGE_PATH"

# AUTOMATION_BASE_URL — the publicly-reachable base URL for the automation
# service.  Appended to callback URLs and injected into each sandbox as
# AUTOMATION_API_URL.  Defaults to the unified ingress.
export AUTOMATION_BASE_URL="${AUTOMATION_BASE_URL:-http://127.0.0.1:${PORT}}"

# AUTOMATION_WORKSPACE_BASE — where automation runs unpack tarballs.
export AUTOMATION_WORKSPACE_BASE="${AUTOMATION_WORKSPACE_BASE:-${STATE_ROOT}/workspaces}"
mkdir -p "$AUTOMATION_WORKSPACE_BASE"

# Default to SQLite so the automation server works out of the box without
# an external PostgreSQL instance. Users can override AUTOMATION_DB_URL to
# point at a real Postgres for production deployments.
if [ -z "${AUTOMATION_DB_URL:-}" ]; then
  AUTOMATION_DB_FILE="${STATE_ROOT}/${CONFIG_AUTOMATION_DB:-automation/automations.db}"
  mkdir -p "$(dirname "$AUTOMATION_DB_FILE")"
  export AUTOMATION_DB_URL="sqlite+aiosqlite:///${AUTOMATION_DB_FILE}"
  log "Using SQLite database: $AUTOMATION_DB_URL"
fi

# The automation server uses uvicorn. Set AUTOMATION_PORT via its CLI.
AUTOMATION_MOD="openhands.automation"
if python -c "import Creanova.automation" 2>/dev/null; then
  AUTOMATION_MOD="Creanova.automation"
fi
if command -v uvicorn >/dev/null 2>&1; then
  uvicorn "${AUTOMATION_MOD}.app:app" \
    --host 0.0.0.0 \
    --port "$AUTOMATION_PORT" &
  PIDS+=($!)
elif python -c "import ${AUTOMATION_MOD}" 2>/dev/null; then
  python -m uvicorn "${AUTOMATION_MOD}.app:app" \
    --host 0.0.0.0 \
    --port "$AUTOMATION_PORT" &
  PIDS+=($!)
else
  log "WARNING: Automation server not found, skipping."
fi

# ── 3. Wait for backends to be ready ─────────────────────────────────────────
wait_for_tcp() {
  local host=$1 port=$2 name=$3 max_wait=${4:-30}
  local elapsed=0
  while ! (echo >/dev/tcp/"$host"/"$port") 2>/dev/null; do
    sleep 1
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$max_wait" ]; then
      log "WARNING: $name on ${host}:${port} did not become ready within ${max_wait}s"
      return 1
    fi
  done
  log "$name is ready on ${host}:${port}"
}

wait_for_port() {
  wait_for_tcp 127.0.0.1 "$1" "$2" "${3:-30}"
}

is_truthy() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    true|1) return 0 ;;
    *) return 1 ;;
  esac
}

# Local source overlay: bind-mount ./build → /opt/agent-canvas/frontend-overlay
# so the Hub image stays a runtime and this tree's UI is applied at start.
FRONTEND_DIR="/opt/agent-canvas/frontend"
if [ -f /opt/agent-canvas/frontend-overlay/index.html ]; then
  FRONTEND_DIR="/opt/agent-canvas/frontend-overlay"
  log "Using local frontend overlay at $FRONTEND_DIR"
else
  log "No local frontend overlay (missing index.html); using image UI"
fi

# When overlay UI is present, optionally send /api through local-gateway
# (auth + SSH hosts). Without overlay, keep /api on agent-server so the
# stock image UI is not stuck behind a login page it does not have.
USE_GATEWAY=0
GATEWAY_ROUTE_ARGS=()
LOCAL_AUTH_ARGS=()
if is_truthy "${OH_LOCAL_AUTH:-false}" && [ -n "${LOCAL_GATEWAY_URL:-}" ]; then
  if [ "$FRONTEND_DIR" = "/opt/agent-canvas/frontend-overlay" ]; then
    USE_GATEWAY=1
    GATEWAY_ROUTE_ARGS=(
      --route "/api=${LOCAL_GATEWAY_URL}"
      --route "/healthz=${LOCAL_GATEWAY_URL}"
    )
    LOCAL_AUTH_ARGS=(--local-auth-enabled)
    log "Local auth gateway: ${LOCAL_GATEWAY_URL}"
  else
    log "OH_LOCAL_AUTH is on but overlay UI is missing; /api stays on agent-server"
  fi
fi
if [ "$USE_GATEWAY" != 1 ]; then
  GATEWAY_ROUTE_ARGS=(--route "/api=http://127.0.0.1:${AGENT_SERVER_PORT}")
fi

wait_for_port "$AGENT_SERVER_PORT" "Agent Server" 60 &
WAIT_PID1=$!
wait_for_port "$AUTOMATION_PORT" "Automation Server" 60 &
WAIT_PID2=$!
wait "$WAIT_PID1" "$WAIT_PID2"

if [ "$USE_GATEWAY" = 1 ]; then
  gw="${LOCAL_GATEWAY_URL#http://}"
  gw="${gw#https://}"
  gw="${gw%%/*}"
  gw_host="${gw%%:*}"
  gw_port="${gw##*:}"
  if [ "$gw_host" = "$gw_port" ]; then
    gw_port=80
  fi
  wait_for_tcp "$gw_host" "$gw_port" "Local gateway" 60 || true
fi

# ── 4. Start static server (frontend + proxy) ────────────────────────────────
log "Starting frontend + proxy on port $PORT..."

# Describe the local runtime services so the frontend can populate the agent's
# <RUNTIME_SERVICES> system-prompt block (without it the agent does not know how
# to reach the local automation backend and falls back to the cloud API). These
# URLs are runtime config (overridable at `docker run`), so unlike the dev
# launchers we cannot bake VITE_RUNTIME_SERVICES_INFO into the image at build
# time — we build the JSON here from the sandbox-facing URLs the entrypoint
# already exports and inject it at serve time via
# static-server.mjs --runtime-services-info. The shape comes from the same
# builder the dev stack uses (scripts/runtime-services-info.mjs).
RUNTIME_SERVICES_INFO="$(node /opt/agent-canvas/runtime-services-info.mjs \
  --mode docker \
  --agent-host-alias 127.0.0.1 \
  --agent-server-url "$AGENT_SERVER_URL" \
  --automation-url "$AUTOMATION_BASE_URL")"

# EFFECTIVE_SESSION_KEY is set above from LOCAL_BACKEND_API_KEY or the persisted api-key.txt
node /opt/agent-canvas/static-server.mjs \
  --port "$PORT" \
  --host :: \
  --dir "$FRONTEND_DIR" \
  --base-path "$AGENT_CANVAS_BASE_PATH" \
  --session-api-key "$EFFECTIVE_SESSION_KEY" \
  --runtime-services-info "$RUNTIME_SERVICES_INFO" \
  "${LOCAL_AUTH_ARGS[@]}" \
  --route "/api/automation=http://127.0.0.1:${AUTOMATION_PORT}" \
  "${GATEWAY_ROUTE_ARGS[@]}" \
  --route "/server_info=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/sockets=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/alive=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/health=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/ready=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/docs=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/redoc=http://127.0.0.1:${AGENT_SERVER_PORT}" \
  --route "/openapi.json=http://127.0.0.1:${AGENT_SERVER_PORT}" &
STATIC_PID=$!
PIDS+=("$STATIC_PID")

# ── 5. (Optional) Public-mode static server ─────────────────────────────────
# When PUBLIC_MODE_PORT is set, start a second static-server instance that
# serves the same frontend WITHOUT injecting the session key into the HTML
# (--auth-required). This is used by auth-mode E2E tests to verify the
# ApiKeyEntryScreen gate, key rotation recovery, etc.
if [ -n "${PUBLIC_MODE_PORT:-}" ]; then
  log "Starting public-mode frontend on port $PUBLIC_MODE_PORT (--auth-required)..."
  node /opt/agent-canvas/static-server.mjs \
    --port "$PUBLIC_MODE_PORT" \
    --host :: \
    --dir "$FRONTEND_DIR" \
    --base-path "$AGENT_CANVAS_BASE_PATH" \
    --auth-required \
    --runtime-services-info "$RUNTIME_SERVICES_INFO" \
    "${LOCAL_AUTH_ARGS[@]}" \
    --route "/api/automation=http://127.0.0.1:${AUTOMATION_PORT}" \
    "${GATEWAY_ROUTE_ARGS[@]}" \
    --route "/server_info=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/sockets=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/alive=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/health=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/ready=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/docs=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/redoc=http://127.0.0.1:${AGENT_SERVER_PORT}" \
    --route "/openapi.json=http://127.0.0.1:${AGENT_SERVER_PORT}" &
  PIDS+=($!)
fi

log "All services started. Unified entry point: http://0.0.0.0:${PORT}/"

# Keep the container alive while the static-server (ingress) is running.
# Backend crashes (agent-server, automation) are tolerated — the proxy
# returns 502 for downed routes, matching the non-Docker path where each
# service is an independent host process.
#
# Pattern: `sleep & wait $!` makes `wait` (a bash builtin) the foreground
# operation.  Unlike a bare `sleep`, the builtin `wait` is interrupted
# immediately when a trapped signal (SIGTERM/SIGINT) arrives, so cleanup()
# fires without delay.  cleanup() calls `exit 0` to terminate after the
# trap returns.  The loop re-checks the static-server PID every 10 s so the
# container exits promptly if the ingress process dies on its own.
while kill -0 "$STATIC_PID" 2>/dev/null; do
  sleep 10 & wait $!
done
log_error "Static server (PID $STATIC_PID) exited"
exit 1
