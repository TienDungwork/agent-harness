# Task — Phase 7 line 123: Smoke tay — session, short-term, TTL, bar, pie, fire/AIOC

Workdir: agent-harness/dong

Implement ONLY this unchecked item from specs/implementation-plan.md:
`- [ ] Smoke tay: session, short-term, TTL, bar, pie, 1 câu fire/AIOC.`

Do NOT implement lines 124–127 (eval run, judge, golden target).

## Goal

Cung cấp **checklist + script smoke** để operator chạy trên Docker stack live (LLM 196 + DB) và xác nhận các case trong `specs/test-plan.md` Live Production.

## Cases bắt buộc (từ test-plan + golden v2)

| # | Case | Câu hỏi mẫu | Kỳ vọng API |
|---|------|-------------|-------------|
| 1 | Session | POST/GET `/api/sessions` | Tạo session, list ≥1, messages API 200 |
| 2 | Short-term | Turn1: "Tên tôi là An." Turn2 cùng session: "Tên tôi là gì?" | Cả 2 stream/chat 200, answer2 có "An" hoặc không empty |
| 3 | TTL | Cùng câu stat 2 lần trong 5 phút | Lần 2 có SSE node `cache` hoặc `cache_hit` trong detail |
| 4 | Bar chart | "Vẽ biểu đồ cột lượt xe theo loại hôm nay" | SSE có `__chart__` với `chart_type` bar (hoặc detail chart) |
| 5 | Pie chart | "Vẽ biểu đồ tròn tỷ lệ loại xe" | SSE có `__chart__` pie |
| 6 | Fire | "Hôm nay có cảnh báo cháy hoặc khói không?" (v2_010) | 200, answer không rỗng |
| 7 | AIOC | "Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?" (v2_014/015) | 200, answer có keyword AIOC/camera/thiết bị |

## Requirements

1. **`scripts/smoke-production.sh`** (bash, executable):
   - Preconditions: gọi `./scripts/verify-docker-self-hosted.sh` trước (hoặc inline health+ping check).
   - Env: `BACKEND_PORT`, `BASE_URL`, `SMOKE_USER_ID` (default `smoke-user-$(date +%s)`).
   - Helper parse SSE stream (python3 inline OK) — collect events, extract `__answer__`, `cache`, `__chart__`.
   - Chạy từng case, in PASS/FAIL + snippet; **tổng kết** pass/fail count; exit 0 chỉ khi tất cả pass.
   - Timeout hợp lý mỗi stream (vd. 120s) — dùng `curl --max-time`.
   - Gửi `session_id`, `user_id` trong `/api/agent/stream` body.

2. **`specs/smoke-manual-checklist.md`** — checklist UI (manual tay) bổ sung script:
   - Sidebar: tạo/chuyển session, preview hiển thị.
   - Chart bar/pie render trên UI (Chart.js canvas).
   - Live graph hover JSON.
   - Link tới `scripts/smoke-production.sh` cho phần API.

3. **`tests/test_phase7_smoke_manual.py`** (offline pytest):
   - Script tồn tại, executable, chứa 7 case keywords/questions.
   - Checklist md tồn tại, mention session/chart/fire/AIOC.
   - Mock TestClient: session create+list; TTL 2nd request mock cache SSE (pattern từ test_memory_ttl_cache).
   - Không cần live LLM/DB trong pytest.

4. **Docs**:
   - Mark `[x]` line 123 in `specs/implementation-plan.md`.
   - Entry in `specs/change-log.md`.
   - Optional: 1 dòng link smoke script trong README (chỉ nếu đã có section eval/checklist — minimal).

5. **Run**:
   ```bash
   pytest tests/test_phase7_smoke_manual.py -q
   pytest -q
   ```

## Constraints

- Không chạy eval golden-30.
- Script phải chạy được khi stack Docker live (user chạy tay); pytest chỉ validate structure + mock.
- PEP 8, plain style.
