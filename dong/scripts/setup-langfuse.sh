#!/usr/bin/env bash
# Khởi động Langfuse (langfuse/) + dong app — user/API keys khớp .env sẵn có.
# Usage:
#   ./scripts/setup-langfuse.sh          # up cả hai stack
#   ./scripts/setup-langfuse.sh --reset  # xóa volume Langfuse, init lại

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LF_COMPOSE="$ROOT/langfuse/docker-compose.yml"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Đã tạo .env từ .env.example"
fi

if [[ ! -f "$ROOT/langfuse/.env" ]]; then
  cp "$ROOT/langfuse/.env.example" "$ROOT/langfuse/.env"
  echo "Đã tạo langfuse/.env từ langfuse/.env.example"
fi

if [[ "${1:-}" == "--reset" ]]; then
  echo "Dừng Langfuse và xóa volume..."
  docker compose -f "$LF_COMPOSE" down -v
fi

echo "Start Langfuse (langfuse/docker-compose.yml)..."
docker compose -f "$LF_COMPOSE" up -d

echo "Build + start dong (frontend + backend)..."
docker compose -f "$ROOT/docker-compose.yml" up --build -d

echo "Chờ Langfuse..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:3000/api/public/health >/dev/null 2>&1; then
    echo "Langfuse OK"
    break
  fi
  if [[ "$i" -eq 60 ]]; then
    echo "Langfuse chưa sẵn sàng — xem: docker compose -f langfuse/docker-compose.yml logs langfuse-web"
    exit 1
  fi
  sleep 3
done

# shellcheck source=/dev/null
source "$ROOT/.env" 2>/dev/null || true

echo ""
echo "=== Sẵn sàng ==="
echo "UI chat:    http://localhost:${FRONTEND_PORT:-8080}"
echo "Langfuse:   http://localhost:3000"
echo "Đăng nhập:  admin@agent-atin.local / Atin@123#"
echo "Project:    agent_ATIN (keys trong .env MONITORING_* / LANGFUSE_*)"
echo ""
echo "Kiểm tra: curl -s http://localhost:${BACKEND_PORT:-8000}/api/health"
