#!/bin/sh
# Patch Langfuse Next bundle: latency hiển thị giây với 3 chữ số thập phân.
set -eu

NEXT_DIR="${1:-/app/web/.next}"
SCALE="${LANGFUSE_LATENCY_DECIMALS:-3}"

if [ ! -d "$NEXT_DIR" ]; then
  echo "patch-latency-decimals: skip — no $NEXT_DIR"
  exit 0
fi

patched=0
for f in $(find "$NEXT_DIR" -type f -name '*.js' 2>/dev/null); do
  if ! grep -q 'formatIntervalSeconds' "$f" 2>/dev/null; then
    continue
  fi
  changed=0
  if grep -q 'formatIntervalSeconds",0,(e,t=2)' "$f" 2>/dev/null \
    || grep -q 'formatIntervalSeconds",0,(a,b=2)' "$f" 2>/dev/null; then
    sed -i \
      -e "s/formatIntervalSeconds\",0,(e,t=2)/formatIntervalSeconds\",0,(e,t=${SCALE})/g" \
      -e "s/formatIntervalSeconds\",0,(a,b=2)/formatIntervalSeconds\",0,(a,b=${SCALE})/g" \
      "$f"
    changed=1
  fi
  if grep -q 'e.toFixed(t)}s' "$f" 2>/dev/null; then
    sed -i "s/e.toFixed(t)}s/e.toFixed(${SCALE})}s/g" "$f"
    changed=1
  fi
  if grep -q 'a.toFixed(b)}s' "$f" 2>/dev/null; then
    sed -i "s/a.toFixed(b)}s/a.toFixed(${SCALE})}s/g" "$f"
    changed=1
  fi
  if [ "$changed" -eq 1 ]; then
    patched=$((patched + 1))
    echo "patched: $f"
  fi
done

# Giảm cache immutable 1 năm (trình duyệt giữ chunk cũ sau khi patch in-place).
if [ -f "$NEXT_DIR/required-server-files.json" ]; then
  sed -i 's/"expireTime":31536000/"expireTime":3600/g' "$NEXT_DIR/required-server-files.json" || true
fi
if [ -f /app/web/server.js ]; then
  sed -i 's/"expireTime":31536000/"expireTime":3600/g' /app/web/server.js || true
fi

echo "patch-latency-decimals: scale=${SCALE}, files=${patched}"
