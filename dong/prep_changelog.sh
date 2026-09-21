#!/bin/bash
TMP_FILE=$(mktemp)
cat << 'LOG' > $TMP_FILE
## 2026-09-21 (Phase 7: Connect UI to data - API Base URL)

### Changed
- `frontend/index.html`: Cập nhật placeholder và hint cho API Base URL trong settings modal cho đúng backend `src`.
- `frontend/app.js`: Thêm kiểm tra validation đơn giản (bắt buộc http:// hoặc https://) khi lưu và kiểm tra sức khỏe trong `checkSystemHealthInModal` và `saveSettings`. Hàm `checkSystemHealthInModal` sử dụng giá trị đang nhập ở input để kiểm tra trực tiếp.
- `tests/test_ui_graph.py`: Thêm test case `test_frontend_settings_api_url_wiring` để kiểm tra việc sử dụng API Base URL và endpoint wiring.
- `specs/implementation-plan.md`: Đánh dấu hoàn thành toàn bộ Phase 7.

LOG
cat specs/change-log.md >> $TMP_FILE
mv $TMP_FILE specs/change-log.md
