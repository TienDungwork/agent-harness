# Hướng Dẫn Spec-Driven Development

Đây là hướng dẫn đơn giản để xây dựng một web app bằng **Cursor Agentic Coding**, một file `AGENTS.md` gọn nhẹ, và **ngrok** để demo/deploy local app ra internet.

---

## 1. Link hữu ích

### Cursor Desktop
Tải Cursor Desktop tại đây:

https://cursor.com/download

Cursor Desktop có sẵn cho macOS, Windows và Linux.

### ngrok
Website ngrok:

https://ngrok.com/

---

Lấy Auth Token để deploy: 

https://dashboard.ngrok.com/get-started/your-authtoken

---


## 2. Mục tiêu của quy trình này

Bạn muốn xây dựng một web app đơn giản mà không làm quy trình trở nên quá phức tạp.

Mục tiêu là sử dụng **spec-driven development**:

1. Viết ý tưởng app trước.
2. Chuyển ý tưởng thành các spec đơn giản.
3. Yêu cầu Cursor triển khai từng task nhỏ một.
4. Theo dõi các thay đổi.
5. Chạy app ở local.
6. Expose app bằng ngrok để demo/test.

Nguyên tắc quan trọng:

> Không yêu cầu Cursor build toàn bộ app trong một lần. Hãy yêu cầu Cursor đọc spec và triển khai từng task nhỏ một.

---

## 3. Cấu trúc project đơn giản nên dùng

Với một app đơn giản, cấu trúc này là đủ:

```txt
my-simple-app/
├── README.md
├── AGENTS.md
├── specs/
│   ├── product-spec.md
│   ├── implementation-plan.md
│   ├── test-plan.md
│   └── change-log.md
├── frontend/
└── backend/
```

Với một project còn đơn giản hơn, chỉ có một app:

```txt
my-simple-app/
├── README.md
├── AGENTS.md
├── specs/
│   ├── product-spec.md
│   ├── implementation-plan.md
│   └── change-log.md
└── src/
```

---

## 4. Vai trò của từng file

| File | Mục đích |
|---|---|
| `README.md` | Giải thích cách cài đặt, chạy và demo app |
| `AGENTS.md` | Hướng dẫn Cursor Agent cách hành xử khi code |
| `specs/product-spec.md` | Định nghĩa mục tiêu app, người dùng, tính năng và acceptance criteria |
| `specs/implementation-plan.md` | Chia app thành các task triển khai nhỏ |
| `specs/test-plan.md` | Định nghĩa cách test app |
| `specs/change-log.md` | Ghi lại những thay đổi sau mỗi lần Cursor triển khai |

---

## 5. Tóm tắt workflow từng bước

| Bước | Việc bạn làm | Prompt nhập vào Cursor | Kết quả kỳ vọng |
|---|---|---|---|
| 1 | Tạo ý tưởng project | Yêu cầu Cursor chuyển ý tưởng app thành spec, chưa code | Cursor tạo các file spec ban đầu |
| 2 | Review spec | Yêu cầu Cursor kiểm tra spec có rõ ràng, đơn giản và tập trung vào MVP không | Cursor cải thiện product spec |
| 3 | Tạo `AGENTS.md` | Yêu cầu Cursor tạo hướng dẫn đơn giản cho coding agent | Cursor tạo rule hành vi khi code |
| 4 | Khởi tạo app | Yêu cầu Cursor chỉ triển khai phần project setup | Cấu trúc app được tạo |
| 5 | Build feature đầu tiên | Yêu cầu Cursor chỉ triển khai task chưa hoàn thành đầu tiên | Feature đầu tiên được triển khai |
| 6 | Test feature | Yêu cầu Cursor test theo acceptance criteria | Bug được phát hiện và sửa |
| 7 | Lặp lại | Yêu cầu Cursor tiếp tục với task chưa hoàn thành tiếp theo | App phát triển từng bước |
| 8 | Thêm hướng dẫn chạy local | Yêu cầu Cursor cập nhật `README.md` với các command local | README có thể dùng được |
| 9 | Thêm hướng dẫn ngrok | Yêu cầu Cursor thêm hướng dẫn demo bằng ngrok | App có thể expose để demo |
| 10 | Review cuối | Yêu cầu Cursor review app so với spec | Báo cáo trạng thái MVP cuối cùng được tạo |

---

# 6. Hướng dẫn chi tiết và prompt cho Cursor

## Bước 1: Tạo spec

### Việc bạn làm
Mở Cursor và mô tả ý tưởng app của bạn.

### Prompt cho Cursor

```txt
I want to build a simple web app using spec-driven development.

App idea:
[Describe the app here]

Before writing any code, create these files:
- README.md
- AGENTS.md
- specs/product-spec.md
- specs/implementation-plan.md
- specs/test-plan.md
- specs/change-log.md

Keep everything simple and MVP-focused.
Do not implement the app yet.
```

### Kết quả kỳ vọng
Cursor tạo cấu trúc tài liệu và spec cơ bản.

---

## Bước 2: Cải thiện Product Spec

### Việc bạn làm
Yêu cầu Cursor làm spec rõ hơn trước khi code.

### Prompt cho Cursor

```txt
Review specs/product-spec.md.

Improve it so it clearly includes:
- app goal
- target users
- core user flow
- features in scope
- features out of scope
- acceptance criteria

Keep it simple.
Do not write code yet.
```

### Kết quả kỳ vọng
Bạn có một product spec MVP rõ ràng, gọn và dễ triển khai.

---

## Bước 3: Cải thiện Implementation Plan

### Việc bạn làm
Chia app thành các task nhỏ có thể build được.

### Prompt cho Cursor

```txt
Review specs/implementation-plan.md.

Rewrite it into small phases:
1. Project setup
2. Core UI
3. Core backend or data logic
4. Connect UI to data
5. Validation and error states
6. Local run instructions
7. ngrok demo setup

Each phase should have clear checklist items.
Do not write code yet.
```

### Kết quả kỳ vọng
Cursor tạo một checklist có thể triển khai từng task một.

---

## Bước 4: Tạo AGENTS.md đơn giản

### Việc bạn làm
Nói cho Cursor biết cách hành xử khi code.

### Prompt cho Cursor

```txt
Create or update AGENTS.md.

The agent should follow these rules:
- Always read the specs before coding.
- Implement only one phase or task at a time.
- Keep the app simple.
- Do not add unnecessary libraries.
- Do not change architecture unless the spec is updated.
- After each implementation, update specs/change-log.md.
- After each implementation, explain how to test the change.

Keep AGENTS.md short and practical.
```

### Kết quả kỳ vọng
Cursor có đủ hướng dẫn để làm việc nhất quán mà không cần `.cursor/rules`.

---

## Bước 5: Triển khai Project Setup

### Việc bạn làm
Bắt đầu code, nhưng chỉ tạo cấu trúc ban đầu.

### Prompt cho Cursor

```txt
Read AGENTS.md and all files in specs/.

Implement only Phase 1 from specs/implementation-plan.md: project setup.

Do not implement any business features yet.

After implementation:
- explain what files were created or changed
- provide commands to run the app
- update specs/change-log.md
```

### Kết quả kỳ vọng
Cursor khởi tạo app của bạn, ví dụ bằng React, Next.js, FastAPI, Express hoặc stack khác mà bạn đã chỉ định.

---

## Bước 6: Triển khai feature đầu tiên

### Việc bạn làm
Chỉ build feature thật đầu tiên.

### Prompt cho Cursor

```txt
Read AGENTS.md and specs/.

Implement only the first unchecked feature in specs/implementation-plan.md.

Before coding, summarize:
- what you will build
- which files you will edit
- how you will test it

After coding:
- update specs/change-log.md
- tell me the exact test steps
```

### Kết quả kỳ vọng
Cursor build một feature mà không vô tình build cả app.

---

## Bước 7: Test theo Acceptance Criteria

### Việc bạn làm
Yêu cầu Cursor kiểm tra feature vừa làm.

### Prompt cho Cursor

```txt
Review the feature you just implemented against the acceptance criteria in specs/product-spec.md and specs/test-plan.md.

Check:
- what passes
- what fails
- what is missing

Fix only issues related to this feature.
Do not add new features.
Update specs/change-log.md after fixing.

```

### Kết quả kỳ vọng
Cursor test và chỉ sửa feature hiện tại.

---

## Bước 8: Lặp lại với feature tiếp theo

### Việc bạn làm
Tiếp tục từng task một.

### Prompt cho Cursor

```txt
Continue with the next unchecked item in specs/implementation-plan.md.

Implement only that item.
Do not modify unrelated files unless necessary.

After implementation:
- mark the task as completed
- update specs/change-log.md
- provide manual test steps

```

### Kết quả kỳ vọng
App của bạn phát triển từng feature một, có kiểm soát.

---

## Bước 9: Thêm hướng dẫn chạy local

### Việc bạn làm
Đảm bảo app có thể chạy trên máy của bạn.

### Prompt cho Cursor

```txt
Update README.md with clear local development instructions.

Include:
- prerequisites
- install commands
- environment variables
- frontend run command
- backend run command if applicable
- local URLs
- troubleshooting notes
- docker deploy

Do not change app logic.
```

### Kết quả kỳ vọng
Bất kỳ ai cũng có thể chạy app local dựa vào README.

---

## Bước 10: Chuẩn bị demo bằng ngrok

### Việc bạn làm
Expose local app ra internet để demo/test.

### Prompt cho Cursor

```txt
Update README.md with a section called "Demo with ngrok".

Explain how to:
- start the frontend locally
- start the backend locally if applicable
- expose the frontend using ngrok
- expose the backend using ngrok if needed
- configure frontend API base URL to use the ngrok backend URL

Use the actual ports used in this project.
Do not change app logic.
```

### Kết quả kỳ vọng
README có command demo bằng ngrok.

Ví dụ command frontend:

```bash
npm run dev
ngrok http 5173
```

Ví dụ command backend:

```bash
uvicorn main:app --reload --port 8000
ngrok http 8000
```

---

## Bước 11: Review cuối trước khi demo

### Việc bạn làm
Yêu cầu Cursor kiểm tra xem MVP đã sẵn sàng chưa.

### Prompt cho Cursor

```txt
Review the entire app against specs/product-spec.md and specs/implementation-plan.md.

Create a final MVP status report with:
- completed features
- missing features
- known bugs
- how to run locally
- how to demo with ngrok
- recommended next improvements

Do not write code unless there is a critical bug.
```

### Kết quả kỳ vọng
Bạn có một checklist rõ ràng trước khi demo app.

---

# 7. Ví dụ AGENTS.md

Dùng nội dung này làm `AGENTS.md` mặc định cho các app đơn giản:

```md
# AGENTS.md

Project này tuân theo simple spec-driven development.

## Nguyên tắc chính
Luôn đọc các file trong `/specs` trước khi code.

## Workflow
Với mỗi task:
1. Đọc các file spec liên quan.
2. Chỉ triển khai một task hoặc một phase tại một thời điểm.
3. Giữ giải pháp đơn giản.
4. Tránh thêm thư viện không cần thiết.
5. Không thay đổi architecture trừ khi spec được cập nhật.
6. Sau khi triển khai, cập nhật `specs/change-log.md`.
7. Giải thích cách test thay đổi.

## Coding Style
- Ưu tiên code đơn giản, dễ đọc.
- Không over-engineer.
- Không thêm feature không liên quan.
- Giữ thay đổi nhỏ và dễ review.

## Testing
Trước khi nói task đã hoàn thành, hãy cung cấp:
- command để chạy app
- các bước test thủ công
- các issue đã biết nếu có
```

---

# 8. Ví dụ Product Spec Template

Tạo file này tại `specs/product-spec.md`:

```md
# Product Spec

## App Name
[Tên app]

## Goal
[App này giải quyết vấn đề gì?]

## Target Users
- [Nhóm người dùng 1]
- [Nhóm người dùng 2]

## Core User Flow
1. User mở app.
2. User thực hiện hành động chính.
3. App hiển thị kết quả.
4. User có thể tiếp tục hoặc reset.

## Features In Scope
- [Feature 1]
- [Feature 2]
- [Feature 3]

## Features Out of Scope
- Authentication
- Payments
- Admin dashboard
- Production cloud deployment

## Acceptance Criteria
- User có thể chạy app local.
- User có thể hoàn thành flow chính.
- User thấy trạng thái success/error rõ ràng.
- App có thể demo bằng ngrok.
```

---

# 9. Ví dụ Implementation Plan Template

Tạo file này tại `specs/implementation-plan.md`:

```md
# Implementation Plan

## Phase 1: Project Setup
- [ ] Initialize project structure
- [ ] Install required dependencies
- [ ] Add basic README
- [ ] Confirm app runs locally

## Phase 2: Core UI
- [ ] Create main page
- [ ] Add input form
- [ ] Add result/display section
- [ ] Add basic styling

## Phase 3: Core Logic
- [ ] Implement main app logic
- [ ] Add validation
- [ ] Add error handling

## Phase 4: Connect UI to Logic
- [ ] Connect form to logic
- [ ] Show loading state if needed
- [ ] Show success/error result

## Phase 5: Testing
- [ ] Test happy path
- [ ] Test empty input
- [ ] Test invalid input
- [ ] Test refresh/reload behavior

## Phase 6: Local Run Guide
- [ ] Update README with install command
- [ ] Update README with run command
- [ ] Add local URL

## Phase 7: ngrok Demo
- [ ] Add ngrok setup instructions
- [ ] Add frontend tunnel command
- [ ] Add backend tunnel command if needed
- [ ] Add demo checklist
```

---

# 10. Ví dụ Change Log Template

Tạo file này tại `specs/change-log.md`:

```md
# Change Log

## YYYY-MM-DD

### Added
- 

### Changed
- 

### Fixed
- 

### Notes
- 
```

---

# 11. Command demo bằng ngrok

## Chỉ có frontend

Nếu app của bạn chỉ có frontend:

```bash
npm run dev
ngrok http 5173
```

Mở HTTPS forwarding URL do ngrok cung cấp.

## Frontend + Backend

Terminal 1: start backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Terminal 2: expose backend

```bash
ngrok http 8000
```

Terminal 3: cấu hình environment cho frontend

```env
VITE_API_BASE_URL=https://your-backend-ngrok-url.ngrok-free.app
```

Terminal 4: start frontend

```bash
cd frontend
npm run dev
```

Terminal 5: expose frontend

```bash
ngrok http 5173
```

Share HTTPS URL của frontend từ ngrok.

---

# 12. Ba prompt quan trọng nhất cho Cursor

## Bắt đầu task tiếp theo

```txt
Read AGENTS.md and specs/.

Implement only the next unchecked task in specs/implementation-plan.md.
Keep the change small.
Update specs/change-log.md after implementation.
```

## Sửa bug

```txt
This feature has a bug:

[Describe bug]

Read the relevant spec first.
Find the root cause.
Fix only this bug.
Do not add unrelated features.
Update specs/change-log.md.
```

## Chuẩn bị demo

```txt
Prepare this project for a local ngrok demo.

Update README.md with exact commands to run the app locally and expose it with ngrok.
Use the actual project ports.
Do not change app logic.
```

---

# 13. Mental model cuối cùng

Bạn là product owner.

Cursor là junior developer.

Spec là hợp đồng.

Change log là bộ nhớ.

ngrok là demo tunnel, không phải production deployment.
