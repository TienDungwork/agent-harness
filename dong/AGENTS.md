# AGENTS.md — agent dong

Hướng dẫn ngắn cho AI agent trong `agent-harness/dong`.

## Trạng thái

- **v7:** Production verified — Docker + `self_hosted` @ 196, smoke 7/7, pytest 595, eval **27/30** (chưa đạt ≥28; residual 018/021/023).
- Phase 1–6 done; Phase 7 còn 1 dòng eval target trong `specs/implementation-plan.md`.

## Specs (tài liệu bắt buộc đọc trước khi code)

1. `specs/product-spec.md` — Yêu cầu nghiệp vụ, luồng xử lý và tiêu chuẩn nghiệm thu.
2. `specs/implementation-plan.md` — Danh sách các phase triển khai tuần tự.
3. `specs/test-plan.md` — Kế hoạch kiểm thử tự động, thủ công và golden-30.
4. `specs/change-log.md` — Nhật ký thay đổi và kết quả review qua từng bước.

## Quy tắc thực thi (Rules)

- Luôn đọc kỹ specs trước khi viết code.
- Thực hiện từng mục chưa hoàn thành (`[ ]`) một cách tuần tự, không nhảy cóc hay gộp nhiều phase.
- Giữ ứng dụng gọn gàng, đúng thiết kế, không tự ý thêm thư viện ngoài hoặc thay đổi kiến trúc.
- Sau mỗi lần triển khai:
  - Đánh dấu hoàn thành `[x]` trong `specs/implementation-plan.md`.
  - Cập nhật chi tiết trong `specs/change-log.md`.
  - Cung cấp các bước kiểm thử thủ công rõ ràng.
- Chế độ chạy chính thức là **Docker**: `docker compose up --build -d`.
- Backend production sử dụng `LLM_BACKEND=self_hosted` trỏ tới `192.168.1.196:18083` (model `qwen3-4b`).

## Kiểm thử nhanh

```bash
cd agent-harness/dong
pytest -q
docker compose up --build -d
./scripts/verify-docker-self-hosted.sh
./scripts/smoke-production.sh
PYTHONPATH=. python eval/run.py   # golden-30 → eval/results/golden-30.md
```
