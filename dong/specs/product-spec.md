# Product Spec — agent dong v4 (MVP)

Chỉ spec. Chưa code.

## App goal

Trợ lý tiếng Việt cho VMS KCN Hưng Phú, một cây code trong `src/` (không còn `backend/`).

1. Trả **số liệu sự kiện** từ nguồn chỉ đọc.
2. Trả **cách dùng VMS** từ tài liệu local (how-to, sự cố, khái niệm), kể cả sơ đồ các bước.
3. Trên UI: **vẽ graph agent theo thời gian thực** — node hiện lần lượt; trỏ node đã chạy thì xem input/output.

LLM local máy 196. Code ngắn kiểu `llm-engineer-demo`. Kết thúc bằng file kết quả 30 câu golden để người dùng chấm.

## Target users

- Vận hành KCN: hỏi tiếng Việt, không viết SQL; nhìn agent đang ở node nào.
- Người review: xem input/output từng node trên UI; chấm `eval/results/golden-30.md`.

## Core user flow

1. Mở UI: cột trái chat (~50% rộng), cột phải khung graph (~50% rộng).
2. Gõ một câu tiếng Việt và gửi.
3. Hệ thống chặn injection. Câu ngoài phạm vi → từ chối. Khung graph bắt đầu nhận sự kiện node.
4. Phân loại:
   - **Số liệu** → tool chỉ đọc (ClickHouse trước; Postgres `agent_readonly` nếu domain chưa có trên CH) → số lấy từ tool.
   - **Cách dùng** → đoạn tài liệu local → trả lời bám đoạn; hỏi “vẽ sơ đồ” → thêm markdown/mermaid.
   - **Khác** → một câu từ chối.
5. Mỗi node xong → UI vẽ/tô node đó. Hover hoặc click node đã done → hiện **input** và **output**.
6. (Tuỳ chọn) Langfuse ghi câu hỏi, câu trả lời, token, latency.

## Features in scope

- Gộp `backend/` vào `src/`, xóa hàm/file trùng. Entry: `src/main.py`.
- `tests/` còn **dưới 10 file**.
- LLM Ollama: `http://192.168.1.196:11434/v1`, model `qwen3-16k-nothink:latest`, cấu hình `.env`.
- Ba nhánh: số liệu, tài liệu VMS, ngoài phạm vi. Tool cố định chỉ đọc. Không text-to-SQL.
- Tài liệu local (kiểu `duy/VMS_doc` + AIOC `https://aioc.atin.vn/devices`).
- Guardrail; không bịa số khi tool trả 0; cache đúng câu trùng; trace mỏng.
- Live graph UI: stream SSE (ưu tiên) `{node_id, status, input?, output?}`; vẽ realtime; hover/click node done → I/O (có thể cắt ~2KB); mở rộng `frontend/` hiện có.
- Eval `eval/datasets/agent_stat/v2.yaml` (30 câu, 18/6/3/3) → `eval/results/golden-30.md`.

## Features out of scope

- Giữ song song `backend/` và `src/` sau khi gộp.
- Web search, multi-agent, text-to-SQL, ghi DB, sửa camera trên AIOC.
- Cache embedding; redesign Docker/UI từ đầu.
- Graph editor kéo-thả, zoom phức tạp, replay nhiều phiên cũ (MVP chỉ phiên hỏi hiện tại).
- Thêm file test làm `tests/` vượt 9 file.

## Acceptance criteria

1. Không còn thư mục `backend/`. Import app chỉ từ `src`.
2. `tests/` có ít hơn 10 file `test_*.py`. `pytest -q` phủ guardrail, nhánh, read-only, API, smoke stream node.
3. Mọi truy vấn dữ liệu chỉ đọc. `INSERT`/`UPDATE`/`DELETE`/`DROP` bị chặn trước DB.
4. How-to không gọi tool thống kê. Số liệu không lấy từ trí nhớ model.
5. Ping LLM `192.168.1.196:11434` thành công trên LAN.
6. Trace có output + latency, hoặc no-op rõ khi tắt monitoring.
7. Một câu hỏi trên UI: khung ~nửa màn hình cập nhật node lần lượt; trỏ node đã chạy thấy input và output.
8. `eval/results/golden-30.md` đủ 30 dòng: đúng/sai, latency, lý do sai (lần đầu không bắt buộc 30/30).
