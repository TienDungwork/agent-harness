# Demo RBAC — đăng nhập & thử phân quyền

## Đăng nhập trên web

1. Mở UI agent (vd. `http://192.168.1.198:8001`) — **hard refresh** (`Ctrl+Shift+R`) nếu pill không mở modal.
2. Topbar → nút **「Chưa đăng nhập」** / **「Đăng nhập để hỏi」** → modal IAM (khi `IAM_REQUIRED=true` modal tự mở).
3. Nếu bấm không phản hồi: `docker compose up -d --force-recreate frontend ai_backend` rồi hard refresh.
4. Bấm chip bộ phận → **tự điền** user + pass (`Atin@123#`, hiện trong modal) → **Đăng nhập**.
5. Pill chuyển xanh, hiện `username · ROLE_GROUP` (vd. `hp_anninh · SECURITY_DEPT`).
6. **Đăng xuất** trong cùng modal để đổi account.

Backend proxy: `POST /api/auth/login`, `GET /api/auth/me` (không gọi IAM từ trình duyệt).

## Điều kiện chạy giống production

Trong `.env` (restart backend sau khi sửa):

```env
IAM_BASE_URL=http://192.168.1.250:21601
IAM_REQUIRED=true
```

- Staging IAM: `:18641`
- Org Hưng Phú: **103** (FE lưu `agent_organization_id`)
- `IAM_REQUIRED=false` → bypass BOARD (local/eval); vẫn có thể login để thử role

## Account thử (mật khẩu: `Atin@123#`)

| User | Role | Thử hỏi |
|------|------|---------|
| `hp_anninh` | SECURITY_DEPT | Cháy/khói, xe → OK; điện năng → deny |
| `hp_moitruong` | ENVIRONMENT_DEPT | Môi trường/điện → OK; cháy/xe → deny |
| `hp_vanhanh` | OPERATIONS_DEPT | Camera/vận hành |
| `hp_banlanhdao` | BOARD_DIRECTOR | Full |
| `hp_orgadmin` | ORG_ADMIN → BOARD | Full |
| `hp_area_oto` / `hp_zone_oto` | AREA/ZONE_ADMIN | Geo hẹp (area 18 / zone 23) |

## Kiểm tra nhanh

1. Login An ninh → hỏi cháy → có trả lời.
2. Cùng session hỏi điện năng → từ chối quyền.
3. Đăng xuất → login Môi trường → hỏi điện → OK.
4. (API) token org 103 + header `X-Organization-Id: 106` → **403**.

Pytest live: `IAM_LIVE=1` + `IAM_TEST_PASSWORD` → `tests/test_v18_iam_live.py`.
