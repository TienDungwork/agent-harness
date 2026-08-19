#!/bin/sh
# Seed hub public key + permanent universal token for the same-host agent.
# Also ensures the host system record exists in Beszel (idempotent).
set -eu

HUB_URL="${HUB_URL:-http://beszel:8090}"
EMAIL="${BESZEL_USER_EMAIL:-admin@creanova.local}"
PASSWORD="${BESZEL_USER_PASSWORD:-admin123}"
SHARED="${SHARED_DIR:-/beszel_shared}"
DATA="${BESZEL_DATA_DIR:-/beszel_data}"
TOKEN_FILE="$SHARED/token"
KEY_FILE="$SHARED/id_ed25519.pub"
SYSTEM_NAME="${BESZEL_SYSTEM_NAME:-atin191}"
SYSTEM_HOST="${BESZEL_SYSTEM_HOST:-192.168.1.250}"
SYSTEM_PORT="${BESZEL_SYSTEM_PORT:-45876}"

mkdir -p "$SHARED"

# Wait for hub to be healthy.
i=0
while [ "$i" -lt 60 ]; do
  if curl -sf "$HUB_URL/api/health" >/dev/null; then
    break
  fi
  i=$((i + 1))
  sleep 2
done
curl -sf "$HUB_URL/api/health" >/dev/null

# Generate token + key if not already present.
if [ -s "$TOKEN_FILE" ] && [ -s "$KEY_FILE" ]; then
  echo "beszel bootstrap: token and key already present, skipping key gen"
else
  i=0
  while [ ! -s "$DATA/id_ed25519" ] && [ "$i" -lt 30 ]; do
    i=$((i + 1))
    sleep 1
  done
  if [ ! -s "$DATA/id_ed25519" ]; then
    echo "beszel bootstrap: hub private key missing" >&2
    exit 1
  fi

  ssh-keygen -y -f "$DATA/id_ed25519" >"$KEY_FILE"

  auth() {
    curl -sf -X POST "$HUB_URL/api/collections/users/auth-with-password" \
      -H "Content-Type: application/json" \
      -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
  }

  AUTH_JSON=""
  if ! AUTH_JSON="$(auth)"; then
    curl -sf -X POST "$HUB_URL/api/beszel/create-user" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null || true
    AUTH_JSON="$(auth)"
  fi

  PB_TOKEN="$(printf '%s' "$AUTH_JSON" | jq -r '.token')"
  if [ -z "$PB_TOKEN" ] || [ "$PB_TOKEN" = "null" ]; then
    echo "beszel bootstrap: auth failed" >&2
    exit 1
  fi

  UT_JSON="$(curl -sf "$HUB_URL/api/beszel/universal-token?enable=1&permanent=1" \
    -H "Authorization: $PB_TOKEN")"
  TOKEN="$(printf '%s' "$UT_JSON" | jq -r '.token')"
  if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    echo "beszel bootstrap: universal token failed" >&2
    exit 1
  fi

  printf '%s\n' "$TOKEN" >"$TOKEN_FILE"
  chmod 644 "$TOKEN_FILE" "$KEY_FILE"
  echo "beszel bootstrap: wrote token and public key"
fi

# Authenticate to get PB_TOKEN (needed for system record management).
AUTH_JSON="$(curl -sf -X POST "$HUB_URL/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
PB_TOKEN="$(printf '%s' "$AUTH_JSON" | jq -r '.token')"
if [ -z "$PB_TOKEN" ] || [ "$PB_TOKEN" = "null" ]; then
  echo "beszel bootstrap: auth failed for system record step" >&2
  exit 1
fi

# Ensure host system record exists in Beszel (idempotent by name).
EXISTING="$(curl -sf \
  "$HUB_URL/api/collections/systems/records?filter=name%3D'$SYSTEM_NAME'&perPage=1" \
  -H "Authorization: $PB_TOKEN" | jq -r '.totalItems')"

if [ "$EXISTING" = "0" ] || [ -z "$EXISTING" ]; then
  TOKEN_VAL="$(cat "$TOKEN_FILE")"
  curl -sf -X POST "$HUB_URL/api/collections/systems/records" \
    -H "Authorization: $PB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$SYSTEM_NAME\",\"host\":\"$SYSTEM_HOST\",\"port\":$SYSTEM_PORT,\"token\":\"$TOKEN_VAL\",\"status\":\"pending\"}" \
    >/dev/null
  echo "beszel bootstrap: created system '$SYSTEM_NAME' ($SYSTEM_HOST:$SYSTEM_PORT)"
else
  # Update host/port in case they changed.
  SYS_ID="$(curl -sf \
    "$HUB_URL/api/collections/systems/records?filter=name%3D'$SYSTEM_NAME'&perPage=1" \
    -H "Authorization: $PB_TOKEN" | jq -r '.items[0].id')"
  curl -sf -X PATCH "$HUB_URL/api/collections/systems/records/$SYS_ID" \
    -H "Authorization: $PB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"host\":\"$SYSTEM_HOST\",\"port\":$SYSTEM_PORT}" \
    >/dev/null
  echo "beszel bootstrap: system '$SYSTEM_NAME' already exists (id=$SYS_ID), host updated"
fi
