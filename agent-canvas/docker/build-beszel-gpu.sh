#!/usr/bin/env bash
# Build custom Beszel hub+agent with container GPU columns.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BESZEL="$(cd "$ROOT/../services/beszel" && pwd)"
mkdir -p "$BESZEL/build"

echo "==> agent"
docker run --rm -v "$BESZEL":/app -w /app -e GOTOOLCHAIN=auto golang:1.26-bookworm \
  go build -buildvcs=false -tags glibc -ldflags '-w -s' -o /app/build/beszel-agent ./internal/cmd/agent

echo "==> web UI"
docker run --rm -v "$BESZEL/internal/site":/site -w /site node:22-bookworm \
  bash -c 'npm ci && npm run build'

echo "==> hub"
docker run --rm -v "$BESZEL":/app -w /app -e CGO_ENABLED=0 golang:1.26-bookworm \
  go build -buildvcs=false -ldflags '-w -s' -o /app/build/beszel ./internal/cmd/hub

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
docker run --rm -v "$BESZEL/build":/src -v "$STAGE":/dst alpine:3.21 \
  sh -c 'cp /src/beszel /dst/beszel && chmod 755 /dst/beszel'
cat >"$STAGE/Dockerfile" <<'EOF'
FROM alpine:3.21
RUN apk add --no-cache ca-certificates
COPY beszel /beszel
VOLUME ["/beszel_data"]
EXPOSE 8090
ENTRYPOINT ["/beszel"]
CMD ["serve", "--http=0.0.0.0:8090"]
EOF
docker build -t creanova/beszel:gpu-containers "$STAGE"
echo "OK: creanova/beszel:gpu-containers + $BESZEL/build/beszel-agent"
