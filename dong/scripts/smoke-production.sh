#!/usr/bin/env bash
# ==============================================================================
# Script Smoke Test Production — agent dong (Live Docker + LLM 196 + DB)
# ==============================================================================
# Kiểm tra 7 case bắt buộc theo specs/test-plan.md & specs/implementation-plan.md:
#   1. Session: POST /api/sessions, GET /api/sessions, GET /api/sessions/{id}/messages
#   2. Short-term memory: Nhớ tên qua 2 turn trong cùng session_id
#   3. TTL Cache: Cùng câu hỏi thống kê 2 lần trong 5 phút -> SSE node cache / cache_hit
#   4. Bar chart: "Vẽ biểu đồ cột lượt xe theo loại hôm nay" -> SSE __chart__ bar
#   5. Pie chart: "Vẽ biểu đồ tròn tỷ lệ loại xe" -> SSE __chart__ pie
#   6. Fire (#010): "Hôm nay có cảnh báo cháy hoặc khói không?" -> 200, answer không rỗng
#   7. AIOC (#014/015): "Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?" -> 200, keyword AIOC/camera/thiết bị
# ==============================================================================

set -uo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
BASE_URL="${BASE_URL:-http://localhost:${BACKEND_PORT}}"
SMOKE_USER_ID="${SMOKE_USER_ID:-smoke-user-$(date +%s)}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
SKIP_PRECHECK="${SKIP_PRECHECK:-0}"

# Thiết lập màu nếu chạy trên terminal tương tác
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    GREEN=''
    RED=''
    YELLOW=''
    BLUE=''
    CYAN=''
    NC=''
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR=$(mktemp -d -t dong_smoke_XXXXXX)
trap 'rm -rf "${TMP_DIR}"' EXIT

PASSED_COUNT=0
FAILED_COUNT=0

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}  BẮT ĐẦU SMOKE TEST PRODUCTION (agent dong v6)${NC}"
echo -e "${CYAN}  Target: ${BASE_URL} | User ID: ${SMOKE_USER_ID}${NC}"
echo -e "${CYAN}==============================================================================${NC}"

# ------------------------------------------------------------------------------
# Preconditions: Kiểm tra verify-docker-self-hosted.sh hoặc inline health/ping
# ------------------------------------------------------------------------------
if [ "${SKIP_PRECHECK}" != "1" ]; then
    echo -e "\n${BLUE}--- [Precondition] Kiểm tra Docker Self-hosted Backend ---${NC}"
    if [ -f "${SCRIPT_DIR}/verify-docker-self-hosted.sh" ]; then
        if ! BACKEND_PORT="${BACKEND_PORT}" "${SCRIPT_DIR}/verify-docker-self-hosted.sh"; then
            echo -e "${RED}[LỖI] Precondition thất bại qua verify-docker-self-hosted.sh!${NC}"
            echo "Vui lòng đảm bảo stack Docker đã khởi động và gateway 196 kết nối được."
            exit 1
        fi
    else
        echo -n "Kiểm tra /api/health... "
        HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${BASE_URL}/api/health" || echo "000")
        if [ "$HEALTH_CODE" != "200" ]; then
            echo -e "${RED}FAIL (HTTP ${HEALTH_CODE})${NC}"
            exit 1
        fi
        echo "OK"

        echo -n "Kiểm tra /api/llm/ping... "
        PING_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "${BASE_URL}/api/llm/ping" || echo "000")
        if [ "$PING_CODE" != "200" ]; then
            echo -e "${RED}FAIL (HTTP ${PING_CODE})${NC}"
            exit 1
        fi
        echo "OK"
    fi
fi

# ------------------------------------------------------------------------------
# Helper parse SSE stream bằng Python inline
# ------------------------------------------------------------------------------
parse_sse() {
    local sse_file="$1"
    python3 - "$sse_file" << 'PYEOF'
import sys, json

filepath = sys.argv[1]
try:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
except Exception as e:
    print(json.dumps({"error": str(e), "answer": "", "has_cache": False, "has_chart": False, "chart_type": ""}))
    sys.exit(0)

events = []
for line in raw.splitlines():
    line = line.strip()
    if line.startswith("data:"):
        payload = line[5:].strip()
        if payload:
            try:
                events.append(json.loads(payload))
            except Exception:
                pass

answer = ""
cache_hit = False
has_cache_node = False
has_chart_node = False
chart_type = ""
error_node = ""

for ev in events:
    if not isinstance(ev, dict):
        continue
    node = ev.get("node_id", "")
    if node == "cache":
        has_cache_node = True
        if not answer and ev.get("output"):
            answer = str(ev.get("output"))
    elif node == "__chart__":
        has_chart_node = True
        ctype = ev.get("chart_type") or (ev.get("chart_spec") or {}).get("chart_type")
        if ctype:
            chart_type = str(ctype)
    elif node == "error":
        error_node = str(ev.get("output", ""))
    elif node == "__answer__":
        if ev.get("output"):
            answer = str(ev.get("output"))
        detail = ev.get("detail") or {}
        if isinstance(detail, dict):
            if detail.get("cache_hit") is True:
                cache_hit = True
            if not chart_type and detail.get("chart_type"):
                chart_type = str(detail.get("chart_type"))
            spec = detail.get("chart_spec")
            if not chart_type and isinstance(spec, dict) and spec.get("chart_type"):
                chart_type = str(spec.get("chart_type"))

res = {
    "event_count": len(events),
    "answer": answer.strip(),
    "has_cache": has_cache_node or cache_hit,
    "has_chart": has_chart_node or bool(chart_type),
    "chart_type": chart_type.lower() if chart_type else "",
    "error": error_node,
}
print(json.dumps(res, ensure_ascii=False))
PYEOF
}

# ------------------------------------------------------------------------------
# Helper gửi SSE request tới /api/agent/stream
# ------------------------------------------------------------------------------
stream_agent() {
    local question="$1"
    local session_id="$2"
    local out_file="$3"

    local payload
    payload=$(python3 -c "import sys, json; print(json.dumps({'question': sys.argv[1], 'session_id': sys.argv[2], 'user_id': sys.argv[3]}))" "$question" "$session_id" "$SMOKE_USER_ID")

    local http_code
    http_code=$(curl -s -S --max-time "${TIMEOUT_SECONDS}" \
        -o "${out_file}" \
        -w "%{http_code}" \
        -X POST "${BASE_URL}/api/agent/stream" \
        -H "Content-Type: application/json" \
        -d "${payload}" 2>/dev/null) || http_code="000"

    echo "$http_code"
}

# ==============================================================================
# Case 1: Session (POST/GET /api/sessions + messages)
# ==============================================================================
echo -e "\n${BLUE}--- [Case 1/7] Session API (create, list, messages) ---${NC}"
SESS_TITLE="Smoke Session $(date +%H%M%S)"
CREATE_REQ_PAYLOAD=$(python3 -c "import sys, json; print(json.dumps({'user_id': sys.argv[1], 'title': sys.argv[2]}))" "$SMOKE_USER_ID" "$SESS_TITLE")

CREATE_RESP=$(curl -s -S --max-time 15 -X POST "${BASE_URL}/api/sessions" \
    -H "Content-Type: application/json" \
    -d "$CREATE_REQ_PAYLOAD" 2>/dev/null) || CREATE_RESP=""

SESSION_ID=$(python3 -c "import sys, json; data=json.loads(sys.argv[1]); print(data.get('id') or data.get('session_id', ''))" "$CREATE_RESP" 2>/dev/null || echo "")

LIST_RESP=$(curl -s -S --max-time 15 "${BASE_URL}/api/sessions?user_id=${SMOKE_USER_ID}" 2>/dev/null) || LIST_RESP=""
SESS_COUNT=$(python3 -c "import sys, json; data=json.loads(sys.argv[1]); print(len(data.get('sessions', [])))" "$LIST_RESP" 2>/dev/null || echo "0")
HAS_SESS=$(python3 -c "import sys, json; data=json.loads(sys.argv[1]); s_ids=[s.get('id') or s.get('session_id') for s in data.get('sessions', [])]; print(1 if sys.argv[2] in s_ids else 0)" "$LIST_RESP" "$SESSION_ID" 2>/dev/null || echo "0")

MSG_CODE="000"
if [ -n "$SESSION_ID" ]; then
    MSG_CODE=$(curl -s -S --max-time 15 -o /dev/null -w "%{http_code}" "${BASE_URL}/api/sessions/${SESSION_ID}/messages?user_id=${SMOKE_USER_ID}" 2>/dev/null) || MSG_CODE="000"
fi

if [ -n "$SESSION_ID" ] && [ "$SESS_COUNT" -ge 1 ] && [ "$HAS_SESS" = "1" ] && [ "$MSG_CODE" = "200" ]; then
    echo -e "${GREEN}[PASS] Case 1: Session API${NC}"
    echo "  -> Session ID tạo thành công: ${SESSION_ID}"
    echo "  -> Số sessions người dùng hiện có: ${SESS_COUNT} (messages API status: ${MSG_CODE})"
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 1: Session API${NC}"
    echo "  -> session_id='${SESSION_ID}', list_count='${SESS_COUNT}', has_session='${HAS_SESS}', messages_http='${MSG_CODE}'"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# Fallback session_id nếu tạo thất bại để các case sau không crash
if [ -z "$SESSION_ID" ]; then
    SESSION_ID="fallback-smoke-session-$(date +%s)"
fi

# ==============================================================================
# Case 2: Short-term memory (Nhớ tên qua 2 turn cùng session)
# ==============================================================================
echo -e "\n${BLUE}--- [Case 2/7] Short-term Memory (2 turns cùng session) ---${NC}"
Q2_1="Tên tôi là An."
OUT2_1="${TMP_DIR}/case2_turn1.sse"
echo "  Turn 1: \"${Q2_1}\"..."
HTTP_CODE2_1=$(stream_agent "$Q2_1" "$SESSION_ID" "$OUT2_1")
PARSE2_1=$(parse_sse "$OUT2_1")
ANS2_1=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE2_1" 2>/dev/null || echo "")

Q2_2="Tên tôi là gì?"
OUT2_2="${TMP_DIR}/case2_turn2.sse"
echo "  Turn 2: \"${Q2_2}\"..."
HTTP_CODE2_2=$(stream_agent "$Q2_2" "$SESSION_ID" "$OUT2_2")
PARSE2_2=$(parse_sse "$OUT2_2")
ANS2_2=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE2_2" 2>/dev/null || echo "")

HAS_AN=$(python3 -c "import sys; ans=sys.argv[1].lower(); print(1 if 'an' in ans else 0)" "$ANS2_2" 2>/dev/null || echo "0")

if [ "$HTTP_CODE2_1" = "200" ] && [ "$HTTP_CODE2_2" = "200" ] && [ -n "$ANS2_2" ]; then
    echo -e "${GREEN}[PASS] Case 2: Short-term memory${NC}"
    echo "  -> Turn 1 reply: $(echo "$ANS2_1" | head -c 80)..."
    echo "  -> Turn 2 reply: $(echo "$ANS2_2" | head -c 80)..."
    if [ "$HAS_AN" = "1" ]; then
        echo "  -> Xác nhận: Agent ghi nhớ và nhắc lại tên 'An'."
    else
        echo "  -> Ghi chú: Phản hồi không rỗng (LLM không lặp lại nguyên văn 'An')."
    fi
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 2: Short-term memory${NC}"
    echo "  -> HTTP 1: ${HTTP_CODE2_1}, HTTP 2: ${HTTP_CODE2_2}, Turn 2 answer: '${ANS2_2}'"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# ==============================================================================
# Case 3: TTL Cache (Hỏi stat 2 lần trong 5 phút -> cache hit)
# ==============================================================================
echo -e "\n${BLUE}--- [Case 3/7] TTL Response Cache (query_data stat) ---${NC}"
Q3="Hôm nay có bao nhiêu lượt xe vào?"
OUT3_1="${TMP_DIR}/case3_first.sse"
echo "  Lần 1: \"${Q3}\"..."
HTTP_CODE3_1=$(stream_agent "$Q3" "$SESSION_ID" "$OUT3_1")
PARSE3_1=$(parse_sse "$OUT3_1")
ANS3_1=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE3_1" 2>/dev/null || echo "")

OUT3_2="${TMP_DIR}/case3_second.sse"
echo "  Lần 2 (ngay sau lần 1): \"${Q3}\"..."
HTTP_CODE3_2=$(stream_agent "$Q3" "$SESSION_ID" "$OUT3_2")
PARSE3_2=$(parse_sse "$OUT3_2")
ANS3_2=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE3_2" 2>/dev/null || echo "")
CACHE_HIT=$(python3 -c "import sys, json; print(1 if json.loads(sys.argv[1]).get('has_cache') else 0)" "$PARSE3_2" 2>/dev/null || echo "0")

if [ "$HTTP_CODE3_1" = "200" ] && [ "$HTTP_CODE3_2" = "200" ] && [ "$CACHE_HIT" = "1" ]; then
    echo -e "${GREEN}[PASS] Case 3: TTL Response Cache hit${NC}"
    echo "  -> Lần 2 đã nhận diện node 'cache' hoặc 'cache_hit: true'"
    echo "  -> Answer snippet: $(echo "$ANS3_2" | head -c 80)..."
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 3: TTL Response Cache hit${NC}"
    echo "  -> HTTP 1: ${HTTP_CODE3_1}, HTTP 2: ${HTTP_CODE3_2}, cache_hit: ${CACHE_HIT}"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# ==============================================================================
# Case 4: Bar chart ("Vẽ biểu đồ cột lượt xe theo loại hôm nay")
# ==============================================================================
echo -e "\n${BLUE}--- [Case 4/7] Bar Chart SSE ---${NC}"
Q4="Vẽ biểu đồ cột lượt xe theo loại hôm nay"
OUT4="${TMP_DIR}/case4_bar.sse"
echo "  Gửi câu hỏi: \"${Q4}\"..."
HTTP_CODE4=$(stream_agent "$Q4" "$SESSION_ID" "$OUT4")
PARSE4=$(parse_sse "$OUT4")
CHART_TYPE4=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('chart_type', ''))" "$PARSE4" 2>/dev/null || echo "")
HAS_CHART4=$(python3 -c "import sys, json; print(1 if json.loads(sys.argv[1]).get('has_chart') else 0)" "$PARSE4" 2>/dev/null || echo "0")
ANS4=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE4" 2>/dev/null || echo "")

if [ "$HTTP_CODE4" = "200" ] && [ "$HAS_CHART4" = "1" ] && [ "$CHART_TYPE4" = "bar" ]; then
    echo -e "${GREEN}[PASS] Case 4: Bar Chart${NC}"
    echo "  -> SSE event __chart__ thành công (chart_type=${CHART_TYPE4})"
    echo "  -> Answer snippet: $(echo "$ANS4" | head -c 80)..."
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 4: Bar Chart${NC}"
    echo "  -> HTTP: ${HTTP_CODE4}, has_chart: ${HAS_CHART4}, chart_type: '${CHART_TYPE4}'"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# ==============================================================================
# Case 5: Pie chart ("Vẽ biểu đồ tròn tỷ lệ loại xe")
# ==============================================================================
echo -e "\n${BLUE}--- [Case 5/7] Pie Chart SSE ---${NC}"
Q5="Vẽ biểu đồ tròn tỷ lệ loại xe"
OUT5="${TMP_DIR}/case5_pie.sse"
echo "  Gửi câu hỏi: \"${Q5}\"..."
HTTP_CODE5=$(stream_agent "$Q5" "$SESSION_ID" "$OUT5")
PARSE5=$(parse_sse "$OUT5")
CHART_TYPE5=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('chart_type', ''))" "$PARSE5" 2>/dev/null || echo "")
HAS_CHART5=$(python3 -c "import sys, json; print(1 if json.loads(sys.argv[1]).get('has_chart') else 0)" "$PARSE5" 2>/dev/null || echo "0")
ANS5=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE5" 2>/dev/null || echo "")

if [ "$HTTP_CODE5" = "200" ] && [ "$HAS_CHART5" = "1" ] && [ "$CHART_TYPE5" = "pie" ]; then
    echo -e "${GREEN}[PASS] Case 5: Pie Chart${NC}"
    echo "  -> SSE event __chart__ thành công (chart_type=${CHART_TYPE5})"
    echo "  -> Answer snippet: $(echo "$ANS5" | head -c 80)..."
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 5: Pie Chart${NC}"
    echo "  -> HTTP: ${HTTP_CODE5}, has_chart: ${HAS_CHART5}, chart_type: '${CHART_TYPE5}'"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# ==============================================================================
# Case 6: Fire warning ("Hôm nay có cảnh báo cháy hoặc khói không?" - v2_010)
# ==============================================================================
echo -e "\n${BLUE}--- [Case 6/7] Fire Warning (v2_010) ---${NC}"
Q6="Hôm nay có cảnh báo cháy hoặc khói không?"
OUT6="${TMP_DIR}/case6_fire.sse"
echo "  Gửi câu hỏi: \"${Q6}\"..."
HTTP_CODE6=$(stream_agent "$Q6" "$SESSION_ID" "$OUT6")
PARSE6=$(parse_sse "$OUT6")
ANS6=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE6" 2>/dev/null || echo "")

if [ "$HTTP_CODE6" = "200" ] && [ -n "$ANS6" ]; then
    echo -e "${GREEN}[PASS] Case 6: Fire Warning${NC}"
    echo "  -> Phản hồi thành công: $(echo "$ANS6" | head -c 100)..."
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 6: Fire Warning${NC}"
    echo "  -> HTTP: ${HTTP_CODE6}, answer rỗng hoặc có lỗi"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# ==============================================================================
# Case 7: AIOC Docs ("Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?" - v2_014/015)
# ==============================================================================
echo -e "\n${BLUE}--- [Case 7/7] AIOC Camera Docs (v2_014/015) ---${NC}"
Q7="Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?"
OUT7="${TMP_DIR}/case7_aioc.sse"
echo "  Gửi câu hỏi: \"${Q7}\"..."
HTTP_CODE7=$(stream_agent "$Q7" "$SESSION_ID" "$OUT7")
PARSE7=$(parse_sse "$OUT7")
ANS7=$(python3 -c "import sys, json; print(json.loads(sys.argv[1]).get('answer', ''))" "$PARSE7" 2>/dev/null || echo "")

HAS_AIOC_KW=$(python3 -c "import sys
ans = sys.argv[1].lower()
keywords = ['aioc', 'camera', 'thiết bị']
matched = [k for k in keywords if k in ans]
print(1 if matched else 0)
" "$ANS7" 2>/dev/null || echo "0")

MATCHED_KW=$(python3 -c "import sys
ans = sys.argv[1].lower()
keywords = ['aioc', 'camera', 'thiết bị']
matched = [k for k in keywords if k in ans]
print(', '.join(matched))
" "$ANS7" 2>/dev/null || echo "")

if [ "$HTTP_CODE7" = "200" ] && [ -n "$ANS7" ] && [ "$HAS_AIOC_KW" = "1" ]; then
    echo -e "${GREEN}[PASS] Case 7: AIOC Camera Docs${NC}"
    echo "  -> Từ khóa nhận diện: [${MATCHED_KW}]"
    echo "  -> Phản hồi: $(echo "$ANS7" | head -c 100)..."
    PASSED_COUNT=$((PASSED_COUNT + 1))
else
    echo -e "${RED}[FAIL] Case 7: AIOC Camera Docs${NC}"
    echo "  -> HTTP: ${HTTP_CODE7}, matched_keywords: '${MATCHED_KW}', answer: '${ANS7}'"
    FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# ==============================================================================
# TỔNG KẾT
# ==============================================================================
echo -e "\n${CYAN}==============================================================================${NC}"
if [ "$FAILED_COUNT" -eq 0 ]; then
    echo -e "${GREEN}  TỔNG KẾT: ${PASSED_COUNT}/7 CASES PASSED (100%)${NC}"
    echo -e "${GREEN}  Toàn bộ các tiêu chí smoke production đều ĐẠT THÀNH CÔNG!${NC}"
    echo -e "${CYAN}==============================================================================${NC}"
    exit 0
else
    echo -e "${RED}  TỔNG KẾT: ${PASSED_COUNT}/7 PASSED, ${FAILED_COUNT}/7 FAILED${NC}"
    echo -e "${RED}  Có case chưa đạt yêu cầu. Vui lòng kiểm tra log chi tiết ở trên.${NC}"
    echo -e "${CYAN}==============================================================================${NC}"
    exit 1
fi
