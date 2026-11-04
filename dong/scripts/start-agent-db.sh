#!/usr/bin/env bash
# Khởi động Postgres agent; nếu AGENT_DB_PORT bận thì thử port kế tiếp (5433..5453).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/resource/db/agent/docker-compose.yml"
ENV_FILE="$ROOT/.env"
CONTAINER="kcn_agent_postgres"
DEFAULT_PORT=5433

port_in_use() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | grep -qE ":${p}\s"
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$p" >/dev/null 2>&1
    return $?
  fi
  return 1
}

pick_port() {
  local start="${1:-$DEFAULT_PORT}"
  local p="$start"
  local limit=$((start + 20))
  while [ "$p" -le "$limit" ]; do
    if ! port_in_use "$p"; then
      echo "$p"
      return 0
    fi
    p=$((p + 1))
  done
  echo "Không tìm được port trống từ $start đến $limit." >&2
  return 1
}

update_env_port() {
  local new_port="$1"
  if [ ! -f "$ENV_FILE" ]; then
    echo "AGENT_DB_PORT=$new_port" >> "$ENV_FILE"
    return
  fi
  if grep -q '^AGENT_DB_PORT=' "$ENV_FILE"; then
    sed -i "s/^AGENT_DB_PORT=.*/AGENT_DB_PORT=$new_port/" "$ENV_FILE"
  else
    echo "AGENT_DB_PORT=$new_port" >> "$ENV_FILE"
  fi
}

if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  mapped="$(docker port "$CONTAINER" 5432/tcp 2>/dev/null | head -1 | sed 's/.*://')"
  echo "Agent Postgres đã chạy: container=$CONTAINER port host=${mapped:-?}"
  echo "DBeaver: localhost / port=${mapped:-5433} / db=kcn_agent / user=atin"
  exit 0
fi

# Load .env nếu có
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -E '^(AGENT_DB_|DB_NAME_AGENT|DB_TIMEZONE)=' "$ENV_FILE" | sed 's/\r$//')
  set +a
fi

WANT_PORT="${AGENT_DB_PORT:-$DEFAULT_PORT}"
if port_in_use "$WANT_PORT"; then
  NEW_PORT="$(pick_port "$WANT_PORT")"
  echo "Port $WANT_PORT đang bận → dùng $NEW_PORT"
  update_env_port "$NEW_PORT"
  export AGENT_DB_PORT="$NEW_PORT"
else
  export AGENT_DB_PORT="$WANT_PORT"
fi

cd "$ROOT"
docker compose -f "$COMPOSE_FILE" up -d

for _ in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U "${AGENT_DB_USER:-atin}" -d "${DB_NAME_AGENT:-kcn_agent}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

HOST_PORT="$(docker port "$CONTAINER" 5432/tcp 2>/dev/null | head -1 | sed 's/.*://')"
echo ""
echo "Agent Postgres OK"
echo "  Host port : ${HOST_PORT:-$AGENT_DB_PORT}"
echo "  Database  : ${DB_NAME_AGENT:-kcn_agent}"
echo "  User      : ${AGENT_DB_USER:-atin}"
echo "  Password  : (AGENT_DB_PASSWORD trong .env)"
echo "DBeaver: Host=localhost Port=${HOST_PORT:-$AGENT_DB_PORT}"
