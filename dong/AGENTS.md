# AGENTS.md — agent dong

Hướng dẫn thực thi chuẩn cho AI agent trong `agent-harness/dong`.

## Trạng thái dự án (v8)

- **Mục tiêu v8:**
  1. Fix lỗi số lượng camera (trả về đúng 10 camera theo AIOC Master Registry).
  2. Hệ thống Human Feedback (Like/Dislike + Lý do + Ảnh đính kèm lưu vào `data/feedback.json` có agent trace).
  3. Token / Chunk Response Streaming (hiển thị câu trả lời gõ chữ dần dần qua SSE).
- **Môi trường chạy:** Docker Compose (`docker compose up -d`).

---

## Tài liệu bắt buộc đọc trước khi code

1. [`specs/product-spec.md`](specs/product-spec.md) — Yêu cầu nghiệp vụ, luồng xử lý và tiêu chí nghiệm thu.
2. [`specs/implementation-plan.md`](specs/implementation-plan.md) — Danh sách 7 phase triển khai tuần tự.
3. [`specs/test-plan.md`](specs/test-plan.md) — Kế hoạch kiểm thử tự động và checklist thủ công.
4. [`specs/change-log.md`](specs/change-log.md) — Nhật ký thay đổi qua từng bước.

---

## Quy tắc thực thi (Rules)

1. **Always read the specs before coding**: Luôn đọc kỹ `specs/product-spec.md` và `specs/implementation-plan.md` trước khi viết bất kỳ dòng code nào.
2. **Implement only one phase or task at a time**: Chỉ thực hiện duy nhất 1 phase hoặc 1 task (`[ ]`) tại một thời điểm. Không nhảy cóc, không gộp nhiều task.
3. **Keep the app simple**: Giữ mã nguồn đơn giản, rõ ràng, tập trung vào phạm vi MVP, không làm quá mức cần thiết (over-engineering).
4. **Do not add unnecessary libraries**: Tận dụng tối đa thư viện và công cụ sẵn có trong dự án, không tự ý cài đặt thêm dependency nếu không bắt buộc.
5. **Do not change architecture unless the spec is updated**: Tuyệt đối không thay đổi kiến trúc hệ thống trừ khi spec đã được thảo luận và cập nhật trước.
6. **After each implementation, update specs/change-log.md**: Sau mỗi lần hoàn thành 1 task, đánh dấu `[x]` trong `specs/implementation-plan.md` và ghi nhận chi tiết vào `specs/change-log.md`.
7. **After each implementation, explain how to test the change**: Luôn giải thích rõ ràng và cung cấp lệnh/kịch bản kiểm thử cụ thể để người dùng có thể tự kiểm tra lại thay đổi.

---

## Lệnh kiểm thử nhanh

```bash
cd agent-harness/dong

# 1. Chạy unit tests
PYTHONPATH=. pytest -q

# 2. Khởi động Docker container
docker compose up -d

# 3. Kiểm tra logs
docker compose logs -f ai_backend
```
