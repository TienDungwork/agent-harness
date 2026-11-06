#!/bin/sh
# Chạy patch latency rồi bàn giao đúng entrypoint gốc Langfuse (+ CMD node server).
set -eu
if [ -x /usr/local/bin/patch-latency-decimals.sh ]; then
  LANGFUSE_LATENCY_DECIMALS="${LANGFUSE_LATENCY_DECIMALS:-3}" /usr/local/bin/patch-latency-decimals.sh || true
fi
exec ./web/entrypoint.sh "$@"
