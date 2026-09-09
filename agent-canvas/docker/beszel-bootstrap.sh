#!/bin/sh
# Bootstrap Beszel hub:
#   1. Generate hub public key + universal token for the local agent (once).
#   2. Enable SMTP (default: local Mailpit) so alert emails can be delivered.
#   3. Sync InfraServer rows from local-gateway SQLite → Beszel systems (every run).
#      Match key: hostname (stable, unique per machine).
set -eu

HUB_URL="${HUB_URL:-http://beszel:8090}"
EMAIL="${BESZEL_USER_EMAIL:-admin@creanova.local}"
PASSWORD="${BESZEL_USER_PASSWORD:-admin123}"
SHARED="${SHARED_DIR:-/beszel_shared}"
DATA="${BESZEL_DATA_DIR:-/beszel_data}"
AGENT_PORT="${BESZEL_AGENT_PORT:-45876}"
# Default SMTP → Mailpit in compose (catch alerts locally). Override via env for real mail.
SMTP_ENABLED="${BESZEL_SMTP_ENABLED:-true}"
SMTP_HOST="${BESZEL_SMTP_HOST:-mailpit}"
SMTP_PORT="${BESZEL_SMTP_PORT:-1025}"
SMTP_USER="${BESZEL_SMTP_USER:-}"
SMTP_PASSWORD="${BESZEL_SMTP_PASSWORD:-}"
SMTP_TLS="${BESZEL_SMTP_TLS:-false}"
SMTP_SENDER_NAME="${BESZEL_SMTP_SENDER_NAME:-Creanova Alerts}"
SMTP_SENDER_ADDRESS="${BESZEL_SMTP_SENDER_ADDRESS:-alerts@creanova.local}"
GW_DB="/canvas_state/agent-canvas/local-gateway.db"
TOKEN_FILE="$SHARED/token"
KEY_FILE="$SHARED/id_ed25519.pub"

mkdir -p "$SHARED"

# ── Wait for hub ─────────────────────────────────────────────────────────────
i=0
while [ "$i" -lt 60 ]; do
  curl -sf "$HUB_URL/api/health" >/dev/null && break
  i=$((i + 1)); sleep 2
done
curl -sf "$HUB_URL/api/health" >/dev/null

# ── Generate token + key (skip if already written) ───────────────────────────
if [ -s "$TOKEN_FILE" ] && [ -s "$KEY_FILE" ]; then
  echo "beszel-bootstrap: credentials already present, skipping key gen"
else
  i=0
  while [ ! -s "$DATA/id_ed25519" ] && [ "$i" -lt 30 ]; do i=$((i+1)); sleep 1; done
  if [ ! -s "$DATA/id_ed25519" ]; then
    echo "beszel-bootstrap: hub private key missing" >&2; exit 1
  fi
  ssh-keygen -y -f "$DATA/id_ed25519" >"$KEY_FILE"

  _auth() {
    curl -sf -X POST "$HUB_URL/api/collections/users/auth-with-password" \
      -H "Content-Type: application/json" \
      -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
  }
  AUTH_JSON=""
  if ! AUTH_JSON="$(_auth)"; then
    curl -sf -X POST "$HUB_URL/api/beszel/create-user" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null || true
    AUTH_JSON="$(_auth)"
  fi
  PB_TOKEN="$(printf '%s' "$AUTH_JSON" | jq -r '.token')"
  [ -n "$PB_TOKEN" ] && [ "$PB_TOKEN" != "null" ] || { echo "beszel-bootstrap: auth failed" >&2; exit 1; }

  UT_JSON="$(curl -sf "$HUB_URL/api/beszel/universal-token?enable=1&permanent=1" \
    -H "Authorization: $PB_TOKEN")"
  TOKEN="$(printf '%s' "$UT_JSON" | jq -r '.token')"
  [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ] || { echo "beszel-bootstrap: universal token failed" >&2; exit 1; }

  printf '%s\n' "$TOKEN" >"$TOKEN_FILE"
  chmod 644 "$TOKEN_FILE" "$KEY_FILE"
  echo "beszel-bootstrap: wrote token and public key"
fi

# ── Auth to Beszel (always needed for system sync) ────────────────────────────
AUTH_JSON="$(curl -sf -X POST "$HUB_URL/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
PB_TOKEN="$(printf '%s' "$AUTH_JSON" | jq -r '.token')"
USER_ID="$(printf '%s' "$AUTH_JSON" | jq -r '.record.id')"
[ -n "$PB_TOKEN" ] && [ "$PB_TOKEN" != "null" ] || { echo "beszel-bootstrap: auth failed" >&2; exit 1; }
[ -n "$USER_ID" ] && [ "$USER_ID" != "null" ] || { echo "beszel-bootstrap: user id missing" >&2; exit 1; }

# ── Superuser tasks (SMTP + optional Keycloak OIDC) ───────────────────────────
# Regular Beszel user cannot open /_/#/settings. Same superuser as SMTP.
SU_JSON="$(curl -sf -X POST "$HUB_URL/api/collections/_superusers/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" || true)"
SU_TOKEN="$(printf '%s' "$SU_JSON" | jq -r '.token // empty')"
if [ -z "$SU_TOKEN" ] || [ "$SU_TOKEN" = "null" ]; then
  echo "beszel-bootstrap: superuser auth failed; skipping SMTP/OIDC configure" >&2
else
  if [ "$SMTP_ENABLED" = "true" ] || [ "$SMTP_ENABLED" = "1" ]; then
    SETTINGS_JSON="$(curl -sf "$HUB_URL/api/settings" -H "Authorization: $SU_TOKEN")"
    PATCHED="$(printf '%s' "$SETTINGS_JSON" | jq \
      --arg host "$SMTP_HOST" \
      --argjson port "$SMTP_PORT" \
      --arg user "$SMTP_USER" \
      --arg pass "$SMTP_PASSWORD" \
      --argjson tls "$SMTP_TLS" \
      --arg sname "$SMTP_SENDER_NAME" \
      --arg saddr "$SMTP_SENDER_ADDRESS" \
      '.smtp.enabled = true
       | .smtp.host = $host
       | .smtp.port = $port
       | .smtp.username = $user
       | .smtp.password = $pass
       | .smtp.tls = $tls
       | .meta.hideControls = false
       | .meta.senderName = $sname
       | .meta.senderAddress = $saddr')"
    if curl -sf -X PATCH "$HUB_URL/api/settings" \
      -H "Authorization: $SU_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$PATCHED" >/dev/null; then
      echo "beszel-bootstrap: SMTP enabled → $SMTP_HOST:$SMTP_PORT (from $SMTP_SENDER_ADDRESS)"
    else
      echo "beszel-bootstrap: SMTP settings patch failed" >&2
    fi
  fi

  # Keycloak OIDC on users collection. Default off (local password users).
  # When disabled, strip a previously enabled provider so the login button disappears.
  OIDC_ENABLED="${BESZEL_OIDC_ENABLED:-false}"
  USERS_JSON="$(curl -sf "$HUB_URL/api/collections/users" -H "Authorization: $SU_TOKEN")"
  if [ "$OIDC_ENABLED" = "true" ] || [ "$OIDC_ENABLED" = "1" ]; then
    KC_BASE="${KEYCLOAK_PUBLIC_URL:-http://192.168.1.191:18180}"
    KC_REALM="${KEYCLOAK_REALM:-creanova}"
    OIDC_CLIENT_ID="${BESZEL_OIDC_CLIENT_ID:-beszel}"
    OIDC_CLIENT_SECRET="${BESZEL_OIDC_CLIENT_SECRET:-beszel-local-secret}"
    AUTH_URL="${KC_BASE%/}/realms/${KC_REALM}/protocol/openid-connect/auth"
    TOKEN_URL="${KC_BASE%/}/realms/${KC_REALM}/protocol/openid-connect/token"
    USERINFO_URL="${KC_BASE%/}/realms/${KC_REALM}/protocol/openid-connect/userinfo"
    OIDC_PATCH="$(printf '%s' "$USERS_JSON" | jq \
      --arg cid "$OIDC_CLIENT_ID" \
      --arg csec "$OIDC_CLIENT_SECRET" \
      --arg aurl "$AUTH_URL" \
      --arg turl "$TOKEN_URL" \
      --arg uurl "$USERINFO_URL" \
      '.oauth2.enabled = true
       | .oauth2.providers = (
           ((.oauth2.providers // []) | map(select(.name != "oidc")))
           + [{
               name: "oidc",
               displayName: "Creanova Keycloak",
               clientId: $cid,
               clientSecret: $csec,
               authURL: $aurl,
               tokenURL: $turl,
               userInfoURL: $uurl,
               pkce: true
             }]
         )
       | .meta.hideControls = false')"
    if curl -sf -X PATCH "$HUB_URL/api/collections/users" \
      -H "Authorization: $SU_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$OIDC_PATCH" >/dev/null; then
      echo "beszel-bootstrap: OIDC enabled → $OIDC_CLIENT_ID @ $KC_BASE (realm $KC_REALM)"
    else
      echo "beszel-bootstrap: OIDC collection patch failed" >&2
    fi
  else
    OIDC_PATCH="$(printf '%s' "$USERS_JSON" | jq \
      '.oauth2.enabled = false
       | .oauth2.providers = ((.oauth2.providers // []) | map(select(.name != "oidc")))')"
    if curl -sf -X PATCH "$HUB_URL/api/collections/users" \
      -H "Authorization: $SU_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$OIDC_PATCH" >/dev/null; then
      echo "beszel-bootstrap: OIDC disabled (password login only)"
    else
      echo "beszel-bootstrap: OIDC disable patch failed" >&2
    fi
  fi

  USERNAME="${BESZEL_USER_USERNAME:-admin}"
  if curl -sf -X PATCH "$HUB_URL/api/collections/users/records/$USER_ID" \
    -H "Authorization: $SU_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"role\":\"admin\"}" >/dev/null; then
    echo "beszel-bootstrap: user username=$USERNAME role=admin"
  else
    echo "beszel-bootstrap: username/role patch failed" >&2
  fi
  USERS_COLL="$(curl -sf "$HUB_URL/api/collections/users" -H "Authorization: $SU_TOKEN")"
  ID_PATCH="$(printf '%s' "$USERS_COLL" | jq \
    '.passwordAuth.identityFields = ["username", "email"]')"
  if curl -sf -X PATCH "$HUB_URL/api/collections/users" \
    -H "Authorization: $SU_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$ID_PATCH" >/dev/null; then
    echo "beszel-bootstrap: password identity fields → username, email"
  else
    echo "beszel-bootstrap: identityFields patch failed" >&2
  fi
fi

# ── Sync InfraServer → Beszel systems ────────────────────────────────────────
if [ ! -f "$GW_DB" ]; then
  echo "beszel-bootstrap: local-gateway DB not found at $GW_DB, skipping system sync"
  exit 0
fi

# Columns: id|name|hostname
SERVERS="$(sqlite3 "$GW_DB" \
  "SELECT id, name, hostname FROM infra_servers WHERE is_active=1 ORDER BY name;")"

if [ -z "$SERVERS" ]; then
  echo "beszel-bootstrap: no active InfraServers found"
  exit 0
fi

# Fetch all existing Beszel systems once to avoid N+1 requests.
ALL_SYSTEMS="$(curl -sf \
  "$HUB_URL/api/collections/systems/records?perPage=200" \
  -H "Authorization: $PB_TOKEN")"

echo "$SERVERS" | while IFS='|' read -r _SRV_ID SRV_NAME SRV_HOST; do
  # Display name = InfraServer.name (label set by user), fallback to hostname
  DISPLAY_NAME="${SRV_NAME:-$SRV_HOST}"

  # Match by host (stable across renames).
  EXISTING_ID="$(printf '%s' "$ALL_SYSTEMS" \
    | jq -r --arg h "$SRV_HOST" '.items[] | select(.host==$h) | .id // empty' \
    | head -1)"

  if [ -z "$EXISTING_ID" ]; then
    # systems.users is required; universal agent token lives in shared volume (not on the record).
    curl -sf -X POST "$HUB_URL/api/collections/systems/records" \
      -H "Authorization: $PB_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"$DISPLAY_NAME\",\"host\":\"$SRV_HOST\",\"port\":\"$AGENT_PORT\",\"users\":[\"$USER_ID\"],\"status\":\"pending\"}" \
      >/dev/null
    echo "beszel-bootstrap: created system '$DISPLAY_NAME' ($SRV_HOST:$AGENT_PORT)"
  else
    curl -sf -X PATCH "$HUB_URL/api/collections/systems/records/$EXISTING_ID" \
      -H "Authorization: $PB_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"$DISPLAY_NAME\",\"host\":\"$SRV_HOST\",\"port\":\"$AGENT_PORT\"}" \
      >/dev/null
    echo "beszel-bootstrap: synced system '$DISPLAY_NAME' ($SRV_HOST:$AGENT_PORT)"
  fi
done

echo "beszel-bootstrap: system sync complete"
