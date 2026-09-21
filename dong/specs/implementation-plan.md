# Implementation Plan — dong v4

Chưa code. Mỗi lần chỉ làm **một phase**. Đánh `[x]` và ghi `specs/change-log.md` khi xong.

Thứ tự: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10.

---

## Phase 1 — Project setup

- [x] Rà `.env.example`: thêm `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` (mặc định `http://192.168.1.196:11434/v1`, `qwen3-16k-nothink:latest`, `ollama`); giữ biến Postgres/ClickHouse read-only nếu đã có.
- [x] Xác nhận entry dự kiến sau gộp: `src/main.py` (chưa xóa `backend/` ở phase này nếu còn phụ thuộc).
- [x] Ghi cấu trúc mục tiêu trong README (src-only, tests < 10, FE 50/50) khớp product-spec.
- [x] Đảm bảo `.gitignore` bỏ qua `.env`, kết quả eval tạm nếu cần.

**Xong khi:** `.env.example` đủ khóa LLM 196; README mô tả đúng hướng v4; chưa bắt buộc chạy app.

---

## Phase 2 — Core UI

- [x] Layout `frontend/`: cột trái chat ≈ 50% rộng, cột phải khung graph trống ≈ 50%.
- [x] Ô nhập câu hỏi + nút gửi (chưa nối backend thật — mock hoặc placeholder OK).
- [x] Khung graph: placeholder “chờ sự kiện node”.
- [x] Panel/tooltip trống sẵn chỗ hiện input/output khi chọn node.

**Xong khi:** mở UI thấy hai cột 50/50; gửi câu chưa cần trả lời thật.

---

## Phase 3 — Gộp `backend/` vào `src/`, gom test

- [x] Chuyển route API từ `backend/main.py` vào `src/main.py`.
- [x] Một `config`, một `llm`, một `tracing` trong `src/`; xóa bản trùng trong `backend/`.
- [x] Xóa hàm không còn caller. Giữ hành vi read-only và guardrail.
- [x] Xóa thư mục `backend/` sau khi import sạch.
- [x] Gom `tests/` từ 14 file xuống **tối đa 9** (gợi ý: guardrails, intent, readonly, docs, llm, trace_cache, api, eval_report, ui_graph).
- [x] Sửa mọi import còn trỏ `backend`.

**Xong khi:** không còn `backend/`; `find tests -name 'test_*.py' | wc -l` < 10; `pytest -q` offline xanh (guardrail, read-only).

---

## Phase 4 — Core backend / data logic

Gom bốn khối trong một phase, checklist theo khối — làm tuần tự trong phase, đánh từng dòng.

### 4a — Nối LLM 196

- [x] Client completion OpenAI-compat trong `src/llm.py` (timeout, lỗi tiếng Việt).
- [x] Hàm/endpoint ping model 196.

### 4b — Graph nhánh

- [x] `classify_intent`: `query_data` | `how_to` | `troubleshoot` | `concept` | `out_of_scope`.
- [x] Guardrail injection chạy trước graph.
- [x] Router: nhánh docs không gọi tool số liệu.
- [x] Mỗi node ghi `node_id` + input/output rút gọn vào state (chuẩn bị stream).

### 4c — Nhánh tài liệu VMS

- [x] Loader markdown local (tối thiểu từ `duy/VMS_doc` + AIOC `/devices` trong golden v2.1).
- [x] Retrieve theo từ khóa (không vector DB MVP).
- [x] Trả lời how-to bám đoạn retrieve; “vẽ sơ đồ” → markdown/mermaid.

### 4d — Nhánh số liệu read-only

- [x] Giữ / nối tool Postgres `agent_readonly`.
- [x] Client ClickHouse chỉ đọc (đếm xe) nếu env CH đủ.
- [x] Cấm SQL ghi. Có `reply_vi` thì copy số, không paraphrase.

**Xong khi:** ping LLM 196 OK; 3 câu mẫu (số liệu / how-to / thời tiết) đúng nhánh; đếm xe gọi tool; how-to không gọi tool đếm; `DELETE` bị chặn.

---

## Phase 5 — Trace, tối ưu, stream sự kiện node

- [x] Một trace / request (input, output, token, latency); tắt bằng env → no-op.
- [x] Cache exact câu trùng (TTL ngắn); lần 2 không gọi LLM khi hit.
- [x] Endpoint stream SSE (ưu tiên): sự kiện `{node_id, status, input?, output?}`.
- [x] Emit sự kiện khi mỗi node graph chuyển running → done.

**Xong khi:** `curl` (hoặc client) thấy node lần lượt; cache hit có log; monitoring tắt không crash.

---

## Phase 6 — Live graph UI

- [x] FE subscribe SSE (hoặc WS) khi gửi câu hỏi.
- [x] Vẽ node lần lượt (running → done) trong khung ~50% phải.
- [x] Hover hoặc click node **done** → hiện input và output (cắt ngắn nếu dài).
- [x] Reset graph khi gửi câu mới.

**Xong khi:** một câu trên UI cập nhật graph realtime và xem được I/O node.

---

## Phase 7 — Connect UI to data

- [x] Nút gửi gọi API ask/chat thật trên `src` (không mock).
- [x] Hiển thị câu trả lời agent ở cột chat.
- [x] Đồng bộ: bắt đầu stream graph cùng request hỏi.
- [x] Cấu hình API base URL trên UI (nếu đã có settings) trỏ đúng backend `src`.

**Xong khi:** end-to-end: hỏi → trả lời số liệu hoặc how-to + graph chạy trên cùng một lượt.

---

## Phase 8 — Validation, error states, Eval 30 câu

- [x] Thông báo lỗi tiếng Việt: LLM down, DB/CH timeout, ngoài phạm vi, injection 400.
- [x] Guardrail output: không bịa số khi tool rỗng/0.
- [x] Chạy `eval/datasets/agent_stat/v2.yaml` (30 câu, 18/6/3/3).
- [x] Ghi `eval/results/golden-30.md`: id, slice, pass/fail, latency_ms, tool, note.
- [x] Judge nhẹ 1–5 (bám nguồn, tiếng Việt, không bịa số) — kiểu `llm-engineer-demo`, không RAGAS đầy đủ.

**Xong khi:** lỗi hiện rõ trên UI/API; file golden đủ 30 dòng, mở được.

---

## Phase 9 — Local run instructions

- [x] README: bước cài `.env`, chạy `src` (uvicorn), phục vụ `frontend/`, cổng.
- [x] Lệnh ping LLM, pytest, eval.
- [x] Ghi phụ thuộc LAN: máy 196 Ollama, CH/PG read-only.

**Xong khi:** người mới theo README chạy được hỏi một câu trên máy local.

---

## Phase 10 — Demo setup

- [ ] Checklist demo: ping 196 → một câu số liệu → một câu how-to → chỉ graph + hover I/O.
- [ ] (Tuỳ chọn) ghi chú LAN URL nếu cần show ngoài máy.
- [ ] Đường dẫn file `eval/results/golden-30.md` trong README để reviewer mở.

**Xong khi:** có mục “Demo” trong README đủ để chạy show 5 phút.

---

## Không làm trong các phase

Giữ `backend/` dự phòng. Graph editor kéo-thả. Web search, swarm, semantic cache, text-to-SQL, ghi DB.
