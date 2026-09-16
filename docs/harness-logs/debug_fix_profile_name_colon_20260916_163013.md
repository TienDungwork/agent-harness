# Pipeline: Allow Ollama-style profile names (colon → hyphen)

- **Pattern**: Known bug (simple)
- **Goal**: Profile Name `qwen3:4b-q4_K_M` không còn bị reject; map sang tên filesystem-safe
- **Started**: 2026-09-16 16:30:13

## Skill Execution Log: 05-fix

- **Skill**: 05-fix
- **Nhiệm vụ**: Auto-sanitize dấu `:` (và ký tự không hợp lệ khác) trong Profile Name khi nhập, vì pattern backend/file store không cho colon
- **Đầu vào nhận được**: User error `Profile name must start with a letter or digit...` khi đặt tên `qwen3:4b-q4_K_M`
- **Files đã sửa**:
  - `agent-canvas/src/utils/derive-profile-name.ts` — thêm `sanitizeProfileNameInput`
  - `agent-canvas/src/components/features/settings/llm-profiles/profile-name-input.tsx` — sanitize trong onChange
  - `agent-canvas/__tests__/utils/derive-profile-name.test.ts` — unit tests sanitize
  - `agent-canvas/__tests__/components/settings/llm-profiles/profile-name-input.test.tsx` — paste Ollama tag
- **Files đã tạo**: Không có
- **Files đã xóa**: Không có
- **Kết quả kiểm tra**: PARTIAL — vitest không chạy được (thiếu `@rolldown/binding-linux-x64-gnu`, `make-i18n` EACCES trên `public/locales`); verified logic bằng node script: `qwen3:4b-q4_K_M` → `qwen3-4b-q4_K_M` (valid)
- **Số lần tự sửa lỗi**: 0
- **Trạng thái**: COMPLETED
- **Ghi chú**: Không nới regex cho phép `:` vì profile lưu thành `{name}.json` (colon invalid trên Windows)

## Skill Execution Log: 07-review

- **Skill**: 07-review
- **Nhiệm vụ**: Review fix profile name colon
- **Đầu vào nhận được**: Diff sanitize + ProfileNameInput
- **Files đã sửa**: Không có
- **Files đã tạo**: Không có
- **Files đã xóa**: Không có
- **Kết quả kiểm tra**: PASS — đúng yêu cầu UX; không mở rộng regex nguy hiểm; sanitize khớp `deriveProfileNameFromModel`; controlled input vẫn validate nếu parent set value bẩn
- **Số lần tự sửa lỗi**: 0
- **Trạng thái**: COMPLETED
- **Ghi chú**: Cần rebuild overlay UI để thấy trên stack Docker

## Tổng kết Pipeline

- **Pattern**: Known bug (simple)
- **Tổng số skills**: 2
- **Hoàn thành**: 2
- **Thất bại**: 0
- **Tổng files đã sửa**: derive-profile-name.ts, profile-name-input.tsx, 2 test files
- **Kết quả kiểm tra tổng thể**: PARTIAL (logic OK, vitest env broken)
- **Timeline**:
  1. 05-fix: COMPLETED — auto-sanitize colon → hyphen
  2. 07-review: COMPLETED — PASS
- **Vấn đề gặp phải**: vitest/rolldown binding + locales EACCES
- **Bước tiếp theo được đề xuất**: Rebuild canvas UI overlay rồi hard-refresh; dùng tên `qwen3-4b-q4_K_M` (hoặc paste bản có colon — UI sẽ tự đổi)
