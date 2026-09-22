# VMS Usage-Guide Knowledge Base

Bộ tài liệu này là nguồn kiến thức có cấu trúc để chatbot hướng dẫn sử dụng VMS bằng tiếng Việt. Đây không phải sổ tay đọc tuần tự: mỗi YAML task card là một đơn vị truy xuất độc lập, tương ứng với một mục tiêu hoặc một lỗi người dùng.

## 1. Mục tiêu

- Trả lời ngắn, đúng trọng tâm và theo từng bước.
- Giữ nguyên tên menu, tab, nút và field đang hiển thị trong VMS.
- Không hướng dẫn chức năng ngoài quyền hoặc module của người dùng.
- Không suy đoán khi tài liệu chưa có bằng chứng.
- Cho phép frontend tái sử dụng route và UI reference để điều hướng/highlight sau này.

## 2. Cấu trúc

```text
VMS_documentation/
├── README.md
├── schema.yaml
├── glossary.yaml
├── index.yaml
├── concepts/
├── how_to/
│   ├── auth/
│   ├── operations/
│   ├── devices/
│   ├── system/
│   ├── organization/
│   └── ai/
└── troubleshooting/
```

- `schema.yaml`: hợp đồng dữ liệu và validation rules.
- `glossary.yaml`: nguồn nhãn UI chuẩn cho chatbot.
- `index.yaml`: catalog mọi card, dùng làm entry point của loader.
- `how_to`: thao tác có trình tự.
- `troubleshooting`: chẩn đoán theo triệu chứng.
- `concepts`: giải thích phạm vi, quyền và cách điều hướng.

## 3. Quy tắc biên tập

### Một card, một intent

Viết “Thêm camera”, “Sửa camera” và “Xóa camera” thành ba card. Không viết một card “Quản lý camera” chứa toàn bộ CRUD.

### Chỉ mô tả điều đã xác minh

Độ ưu tiên nguồn:

1. Component/page hiện hành.
2. i18n hiện hành.
3. Route và guard.
4. Test frontend.
5. Tài liệu mô tả cũ.

Tài liệu cũ không đủ để đánh dấu card là `published`.

### Tên UI phải chính xác

Giữ đúng chữ hoa/thường của `label`; khai báo `i18n_key` nếu có. Không dịch lại theo cảm tính. Nếu component chưa có selector ổn định, đặt `element_id: null`.

### Không ghi thông tin môi trường

Không đưa vào card:

- Host, IP, port hoặc URL triển khai.
- Token, tài khoản, mật khẩu.
- Tên container hay lệnh restart dịch vụ.
- Dữ liệu khách hàng thật.

Route tương đối như `/monitoring` được phép.

### Hành động phá hủy

Card xóa phải:

- Nêu rõ đối tượng bị xóa.
- Nhắc kiểm tra đối tượng đã chọn.
- Bao gồm bước xác nhận.
- Mô tả kết quả sau khi xóa.

## 4. Trạng thái card

- `published`: đủ bằng chứng để chatbot production sử dụng.
- `needs_review`: có ích nhưng còn chi tiết cần kiểm chứng.
- `draft`: chưa dùng để trả lời.
- `deprecated`: đã thay thế, loader phải bỏ qua.

Chỉ ingest `published` theo mặc định.

## 5. Cách ingest cho RAG

### Loader

1. Đọc `index.yaml`.
2. Chọn card có `status: published` và locale phù hợp.
3. Đọc file được khai báo trong `file`.
4. Kiểm tra schema, ID và liên kết trước khi index.

### Nội dung embedding

Với `how_to`, ghép:

```text
title
intent
aliases
summary
steps[].say
tags
```

Với `troubleshooting`, ghép:

```text
title
intent
aliases
summary
symptoms
checks[].if
checks[].then
tags
```

Với `concept`, ghép `title`, `intent`, `aliases`, `answer`, `tags`.

Không embed `sources`, `i18n_key`, `element_id` hoặc ghi chú kiểm chứng.

### Metadata filter

Lưu và lọc theo:

- `status`, `locale`, `module`, `type`
- `roles`, `features`
- `route`, `tags`
- `version`, `last_verified`

Nếu phiên chatbot biết role và feature của user, lọc trước khi vector search. Nếu không biết, chatbot phải trình bày điều kiện quyền trong câu trả lời.

### Retrieval

- Phân loại câu hỏi thành thao tác, xử lý lỗi hoặc khái niệm trước khi xếp hạng; chỉ ưu tiên `troubleshooting` khi câu hỏi có triệu chứng hoặc ý nghĩa lỗi.
- Ưu tiên exact/lexical match trên `intent` và `aliases`.
- Sau đó dùng semantic search.
- Không hợp nhất các card có intent khác nhau chỉ vì cùng module.
- Dùng tối đa ba card: một card chính và tối đa hai card liên quan.
- Nếu không có card đủ tin cậy, dùng fallback ngoài phạm vi.

## 6. Policy sinh câu trả lời

### How-to

```text
[summary]

1. [steps[0].say]
2. [steps[1].say]
...

[precondition hoặc note quan trọng nếu cần]
```

Không thêm bước ngoài card. Chỉ hiển thị route khi user hỏi đường dẫn hoặc cần phân biệt màn hình.

### Troubleshooting

Hỏi hoặc kiểm tra theo đúng thứ tự. Dừng ngay khi gặp `stop_when`. Không hướng dẫn restart hạ tầng cho người dùng cuối.

### Concept

Trả lời từ `answer`, sau đó gợi ý tối đa hai card trong `related`.

### Fallback bắt buộc

Khi không có card phù hợp:

> Tôi chưa có hướng dẫn đã được xác minh cho thao tác này. Bạn hãy cho biết tên màn hình hoặc nút đang thấy; nếu đây là chức năng bị ẩn, vui lòng kiểm tra quyền và module với quản trị viên.

Không được tự bịa tên menu, nút, field, API hoặc nguyên nhân lỗi.

## 7. Context nên truyền từ frontend

Để giảm trả lời sai, frontend nên gửi kèm:

- Route hiện tại.
- Locale.
- Role/capability.
- Danh sách feature được bật.
- Mã module AI hiện tại.
- Card hoặc dialog đang mở, nếu có.

Không gửi password, token hoặc nội dung nhạy cảm vào truy vấn RAG.

## 8. UI guidance

Mỗi bước có thể chứa:

```yaml
ui:
  label: "Giám Sát Trực Tiếp"
  i18n_key: "sidebar.liveMonitoring"
  element_id: null
```

`element_id: null` nghĩa là UI chưa có selector ổn định; frontend không được tự suy ra selector từ label. Khi thêm selector, giữ nội dung `say` và route không đổi nếu nghiệp vụ không đổi.

## 9. Quy trình cập nhật

1. Xác định UI/route thay đổi.
2. Tìm card theo source hoặc module trong index.
3. Cập nhật nhãn/bước và tăng `version`.
4. Cập nhật `last_verified`.
5. Validate YAML, liên kết và dữ liệu nhạy cảm.
6. Review trước khi đổi trạng thái thành `published`.
7. Re-index các card thay đổi.

Nếu tính năng bị gỡ, chuyển card sang `deprecated`; không xóa ngay vì log hội thoại cũ có thể còn tham chiếu ID.

## 10. Checklist trước khi publish một card

- [ ] Một intent duy nhất.
- [ ] Có ít nhất ba aliases tự nhiên.
- [ ] Route và điều kiện quyền/feature chính xác.
- [ ] Mỗi bước dùng đúng nhãn UI.
- [ ] Không có bước suy đoán từ tài liệu cũ.
- [ ] Có ít nhất một source code/i18n/test.
- [ ] Liên kết `related` và `then` tồn tại trong index.
- [ ] Không chứa URL/IP/secret/dữ liệu thật.
- [ ] `version` và `last_verified` đã cập nhật.

## 11. Giới hạn đã xác minh của UI hiện tại

- `Quản lý sự kiện` có thể bị ẩn khỏi sidebar bởi cờ giao diện riêng dù route và feature tồn tại.
- FACE chưa có tab/component Tra cứu hành trình; không ingest card tương ứng cho production.
- Một số phần của INTRUSION và BEHAVIOR đang dùng dữ liệu mô phỏng.
- Một số tab cấu hình FIRE, ZONE hoặc CROWD có code legacy nhưng không được menu AI hiện hành expose.
- Không dùng việc còn i18n key hoặc component registry cũ làm bằng chứng rằng người dùng truy cập được tính năng.
