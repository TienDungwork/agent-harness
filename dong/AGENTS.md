# AGENTS.md

Hướng dẫn và quy tắc phát triển dành cho Coding Agent trong dự án `kcn_hungphu_agent` (agent_stat_v3).

## Nguyên Tắc Cốt Lõi

1. **Luôn đọc Spec trước khi code (Always read the specs before coding)**:
   - Luôn đọc các tài liệu trong thư mục `/specs` (`product-spec.md`, `implementation-plan.md`, `test-plan.md`) trước khi bắt đầu bất kỳ task nào.

2. **Chỉ triển khai một phase hoặc một task tại một thời điểm (Implement only one phase or task at a time)**:
   - Triển khai tuần tự theo đúng checklist trong `specs/implementation-plan.md`.
   - Không nhảy cóc phase hoặc gộp nhiều task lớn làm một.

3. **Giữ ứng dụng đơn giản (Keep the app simple)**:
   - Ưu tiên giải pháp tinh gọn, dễ đọc, dễ bảo trì (tham khảo `llm-engineer-demo`).
   - Không over-engineer, không viết code phức tạp quá mức cần thiết.

4. **Không thêm thư viện không cần thiết (Do not add unnecessary libraries)**:
   - Tận dụng tối đa các thư viện có sẵn trong `requirements.txt`.
   - Không tự ý cài đặt thêm package ngoài trừ khi spec yêu cầu rõ ràng.

5. **Không thay đổi kiến trúc trừ khi Spec được cập nhật (Do not change architecture unless the spec is updated)**:
   - Tuân thủ ranh giới phân tách 2 tầng: `frontend/` (Claude UI) và `ai_backend/` (FastAPI, ReAct Agent).
   - **Giữ nguyên kiến trúc ReAct Agent hiện tại** (`build_react_subgraph`: `seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`) cho 8 domain sự kiện VMS để dễ dàng so sánh hiệu năng.

6. **Cập nhật `specs/change-log.md` sau mỗi lần triển khai (After each implementation, update specs/change-log.md)**:
   - Ghi lại ngắn gọn, rõ ràng: những file đã tạo/sửa (`Added`, `Changed`), và kết quả kiểm thử (`Verified`).
   - Đánh dấu `[x]` vào checklist tương ứng trong `specs/implementation-plan.md`.

7. **Giải thích cách kiểm thử sau mỗi lần triển khai (After each implementation, explain how to test the change)**:
   - Cung cấp câu lệnh chạy ứng dụng cụ thể.
   - Hướng dẫn các bước kiểm thử thủ công và kịch bản test tương ứng.
   - Nêu rõ các issue đã biết (nếu có).

---

## Lưu Ý Bổ Sung Cho Dự Án

- **Bảo Mật Secrets**: Tuyệt đối không commit API key thật (`sk-proj-...`, `lgw_...`) hoặc mật khẩu DB vào git hay `.env.example`.
- **Langfuse Credentials**: Mật khẩu đăng nhập mặc định cho Langfuse Dashboard là `Atin@123#` (User: `admin@agent-atin.local`).
- **Graph Visualization**: Sau khi hoàn thành toàn bộ code, chạy lệnh cập nhật sơ đồ `python3 -m src.agent.graph` (`graph.png`, `graph_diagram.html`).