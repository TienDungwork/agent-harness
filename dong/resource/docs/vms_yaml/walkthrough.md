# Walkthrough — VMS Usage-Guide Knowledge Base

Ngày xác minh: 2026-09-16

## Kết quả

Bộ knowledge base đã được tạo theo task-card format và đối chiếu với frontend, route, i18n và test hiện hành.

- Tổng số card: **42**
- `published`: **40**
- `needs_review`: **2**
- How-to: **34**
- Troubleshooting: **5**
- Concept: **3**
- Tham chiếu i18n đã kiểm tra: **195**

## Đối chiếu với Success Criteria

### SC01 — Foundation

Đạt:

- `README.md`
- `schema.yaml`
- `glossary.yaml`
- `index.yaml`

### SC02 — Tối thiểu 24 card và 10 nhóm

Đạt: 42 card phủ xác thực, điều hướng, dashboard, live monitoring, playback, events, camera, system, organization, AI và troubleshooting.

### SC03 — ID, source, intent và aliases

Đạt:

- ID không trùng.
- Mọi card có intent.
- Mọi card có ít nhất ba aliases.
- Mọi source path đã được kiểm tra tồn tại.

### SC04 — Nhãn và route

Đạt cho 40 card `published`.

Nhãn được đối chiếu với các locale tiếng Việt; route và guard được đối chiếu với `App.jsx`, `Sidebar.jsx` và component tương ứng.

### SC05 — Liên kết chéo

Đạt: toàn bộ `related` trỏ tới ID tồn tại trong index.

### SC06 — Dữ liệu nhạy cảm

Đạt: không phát hiện URL môi trường, địa chỉ IP, token hoặc secret trong card.

### SC07 — Ingest và fallback

Đạt: README mô tả loader, text embedding, metadata filter, phân loại type, retrieval, generation và fallback bắt buộc.

## Kiểm thử retrieval

Một bộ xếp hạng lexical intent-aware tối giản được chạy trong container để kiểm tra 20 cách hỏi:

1. đăng nhập VMS
2. tôi quên mật khẩu
3. xem cam trực tiếp
4. đổi layout camera
5. chụp snapshot live
6. xem lại camera
7. xuất clip playback
8. lọc cảnh báo theo trạng thái
9. xem ảnh chi tiết sự kiện
10. tiếp nhận xử lý cảnh báo
11. camera bị đen
12. timeline không có bản ghi
13. thêm camera mới
14. sửa cấu hình camera
15. xóa camera khỏi hệ thống
16. thêm tài khoản người dùng
17. phân quyền user
18. tạo zone mới
19. đăng ký khuôn mặt nhân viên
20. tìm hành trình xe theo biển số

Kết quả: **20/20 truy vấn trả đúng card mong đợi**.

Lần chạy đầu cho thấy câu hỏi thao tác có thể cạnh tranh với troubleshooting nếu chỉ dùng token overlap. README đã bổ sung yêu cầu phân loại câu hỏi theo type trước khi xếp hạng; alias “xem cam trực tiếp” cũng được bổ sung cho cách gọi tự nhiên.

## Hai card không ingest production

### Tra cứu hành trình khuôn mặt

`how_to/ai/search-face-journey.yaml` có trạng thái `needs_review`.

Lý do: i18n còn nhãn liên quan nhưng bộ tab FACE và registry hiện hành không cung cấp component journey. Card ghi rõ giới hạn để ngăn chatbot bịa hướng dẫn.

### Cấu hình kênh nhận cảnh báo

`how_to/system/configure-alert-channel.yaml` có trạng thái `needs_review`.

Lý do: giao diện xác minh được thao tác bật/tắt kênh, nhưng quy trình cấu hình kết nối và kiểm tra nhận cảnh báo thực tế chưa đủ đồng nhất để công bố toàn bộ.

`index.yaml` chỉ ingest `published`, vì vậy hai card trên tự động bị loại khỏi production corpus.

## Những phần không được đưa vào card

- IP, port và URL của staging/production.
- Lệnh restart container hoặc thao tác hạ tầng.
- Tuyên bố hiệu năng/độ chính xác không được UI chứng minh.
- Chức năng được mô tả trong tài liệu cũ nhưng không còn component hiện hành.
- API action cho chatbot tự thao tác.

## Hướng tích hợp tiếp theo

1. Loader đọc `index.yaml` và chỉ ingest `published`.
2. Lưu role, feature, route và module trong metadata.
3. Phân loại câu hỏi thành `how_to`, `troubleshooting` hoặc `concept`.
4. Exact match intent/aliases trước semantic search.
5. Dùng policy trả lời trong README để khóa chatbot vào nội dung card.
6. Thu thập câu hỏi không match để bổ sung card, không để LLM tự suy đoán.
