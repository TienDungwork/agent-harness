#!/usr/bin/env bash
# Build custom Beszel hub + agent images (GPU / per-container metrics).
# Images are LOCAL ONLY — not on Docker Hub. Must run on every new machine.
#
# Usage (from agent-canvas/):
#   bash docker/build-beszel-gpu.sh
#
# Produces:
#   creanova/beszel:gpu-containers
#   creanova/beszel-agent:gpu-containers
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BESZEL="$(cd "$ROOT/../services/beszel" && pwd)"
mkdir -p "$BESZEL/build"

echo "==> agent binary"
docker run --rm -v "$BESZEL":/app -w /app -e GOTOOLCHAIN=auto golang:1.26-bookworm \
  go build -buildvcs=false -tags glibc -ldflags '-w -s' -o /app/build/beszel-agent ./internal/cmd/agent

echo "==> web UI"
docker run --rm -v "$BESZEL/internal/site":/site -w /site node:22-bookworm \
  bash -c 'npm ci && npm run build'

echo "==> hub binary"
docker run --rm -v "$BESZEL":/app -w /app -e CGO_ENABLED=0 golang:1.26-bookworm \
  go build -buildvcs=false -ldflags '-w -s' -o /app/build/beszel ./internal/cmd/hub

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

echo "==> hub image creanova/beszel:gpu-containers"
docker run --rm -v "$BESZEL/build":/src -v "$STAGE":/dst alpine:3.21 \
  sh -c 'cp /src/beszel /dst/beszel && chmod 755 /dst/beszel'
cat >"$STAGE/Dockerfile.hub" <<'EOF'
FROM alpine:3.21
RUN apk add --no-cache ca-certificates
COPY beszel /beszel
VOLUME ["/beszel_data"]
EXPOSE 8090
ENTRYPOINT ["/beszel"]
CMD ["serve", "--http=0.0.0.0:8090"]
EOF
docker build -f "$STAGE/Dockerfile.hub" -t creanova/beszel:gpu-containers "$STAGE"

# services/beszel/.dockerignore excludes build/ — stage the agent binary so COPY works.
echo "==> agent image creanova/beszel-agent:gpu-containers"
cp "$BESZEL/build/beszel-agent" "$STAGE/beszel-agent"
cat >"$STAGE/Dockerfile.agent" <<'EOF'
FROM henrygd/beszel-agent-nvidia:latest
COPY beszel-agent /agent
EOF
docker build -f "$STAGE/Dockerfile.agent" -t creanova/beszel-agent:gpu-containers "$STAGE"

echo "OK:"
echo "  creanova/beszel:gpu-containers"
echo "  creanova/beszel-agent:gpu-containers"
