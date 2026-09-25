#!/usr/bin/env bash
# ==============================================================================
# Script verify Docker stack with LLM_BACKEND=self_hosted (192.168.1.196:18083)
# ==============================================================================

set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
BASE_URL="http://localhost:${BACKEND_PORT}"

echo "=== Kiểm tra Docker Self-hosted Backend (${BASE_URL}) ==="

# 1. Kiểm tra /api/health
echo -n "[1/2] Kiểm tra /api/health... "
HEALTH_RESP=$(curl -sf "${BASE_URL}/api/health" 2>&1) || {
    echo "FAIL"
    echo "LỖI: Không kết nối được tới ${BASE_URL}/api/health. Đảm bảo docker compose đã khởi động."
    exit 1
}

LLM_BACKEND=$(echo "$HEALTH_RESP" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('llm_backend', ''))" 2>/dev/null || echo "")
ACTIVE_MODEL=$(echo "$HEALTH_RESP" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('active_model', ''))" 2>/dev/null || echo "")

if [ "$LLM_BACKEND" != "self_hosted" ]; then
    echo "FAIL"
    echo "LỖI: llm_backend mong đợi 'self_hosted', nhưng nhận được '${LLM_BACKEND}'"
    echo "Phản hồi: $HEALTH_RESP"
    exit 1
fi
echo "OK (llm_backend=${LLM_BACKEND}, active_model=${ACTIVE_MODEL})"

# 2. Kiểm tra /api/llm/ping
echo -n "[2/2] Kiểm tra /api/llm/ping... "
PING_RESP=$(curl -sf "${BASE_URL}/api/llm/ping" 2>&1) || {
    echo "FAIL"
    echo "LỖI: Gọi ${BASE_URL}/api/llm/ping thất bại. Gateway 192.168.1.196:18083 không phản hồi hoặc MODEL_API_KEY chưa hợp lệ."
    exit 1
}

PING_STATUS=$(echo "$PING_RESP" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', ''))" 2>/dev/null || echo "")
PING_MODEL=$(echo "$PING_RESP" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('model', ''))" 2>/dev/null || echo "")
PING_BACKEND=$(echo "$PING_RESP" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('backend', ''))" 2>/dev/null || echo "")

PING_STATUS_LOWER=$(echo "$PING_STATUS" | tr '[:upper:]' '[:lower:]')

if [ "$PING_STATUS_LOWER" != "ok" ]; then
    echo "FAIL"
    echo "LỖI: ping status không phải 'ok' (nhận được: '${PING_STATUS}')"
    echo "Phản hồi: $PING_RESP"
    exit 1
fi
echo "OK (status=${PING_STATUS}, backend=${PING_BACKEND}, model=${PING_MODEL})"

echo "=== Xác minh thành công: Docker stack sẵn sàng phục vụ với backend self_hosted ==="
exit 0
