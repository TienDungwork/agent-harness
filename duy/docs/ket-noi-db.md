# Kết nối PostgreSQL

Nguồn dữ liệu cho Data Agent. Chốt ngày **2026-09-14**: dùng cùng Postgres với `vinhqd/agent`.

Password **không ghi trong file này**. Lấy `DB_PASSWORD` từ `~/vinhqd/agent/.env`, copy vào `.env` của project `duy` khi làm Phase 3. Không commit `.env`.

---

## Kết nối

| Mục | Giá trị |
|-----|---------|
| Host | `192.168.1.200` |
| Port | `18644` (không phải 5432) |
| User | `vinhdq` |
| Quyền | CONNECT được; **chưa GRANT SELECT** trên bảng nghiệp vụ (2026-09-14) |
| Password | `DB_PASSWORD` trong `.env` |
| Database | Không cố định 1 DB — chọn theo câu hỏi |

Kết nối bằng tham số rời (`host` / `port` / `user` / `password` / `dbname`). Không dùng URL `postgresql://user:pass@host` vì mật khẩu có thể chứa `@`.

```text
Python / LangGraph
        ↓
192.168.1.200:18644
        ↓
PostgreSQL (user vinhdq, read-only)
        ↓
Chọn database: anomaly | smart_face | its | vms_db | ...
```

Biến môi trường:

```bash
DB_HOST=192.168.1.200
DB_PORT=18644
DB_USER=vinhdq
DB_PASSWORD=   # copy từ ~/vinhqd/agent/.env — không commit
```

`DB_NAME` không set một lần. Tool/query nhận `dbname` theo dataset.

---

## Các database nghiệp vụ

Theo catalog `vinhqd/agent/catalog/datasets.yaml` (đã verify trên `.200`):

| Database | Bảng chính | Nội dung |
|----------|------------|----------|
| `anomaly` | `anomaly_event` | Sự kiện bất thường |
| `smart_face` | `smf_face_events` | Nhận diện khuôn mặt |
| `its` | `plate_event`, `plate_violation_event` | Biển số, vi phạm giao thông |
| `firesmoke` | `fire_smoke_event` | Cháy / khói |
| `footfall` | `footfall_event` | Đếm người |
| `ppe` | `ppe_event` | Bảo hộ lao động |
| `thermal_db` | `thermal_alert`, `thermal_reading` | Cảnh báo / số đo nhiệt |
| `virtual_fence` | `zone_event`, `zone_incident` | Hàng rào ảo |
| `vms_db` | `ai_event` | Sự kiện AI tổng hợp (có thể rỗng) |

Liệt kê DB trên server: kết nối `dbname=postgres` rồi `SELECT datname FROM pg_database`.

---

## Không dùng cho Agent này

| Nguồn | Host:port | Lý do |
|-------|-----------|--------|
| VMS local `vms_xaphuong` | `127.0.0.1:5429` user `dev` | DB khác, không phải production `.200` |
| SQLite `vinhqd/agent/data/agent.db` | local file | Chat/ticket của svc-agent, không phải data camera |

---

## An toàn khi nối

- User `vinhdq` **CONNECT được**, `SELECT 1` trên database `postgres` thành công.
- Ngày 2026-09-14: **chưa GRANT SELECT** trên bảng nghiệp vụ (`anomaly_event`, `camera`, `plate_event`, …) → Agent sinh SQL được nhưng execute bị `permission denied`.
- Cần DBA (chạy bằng superuser trên `.200`):

```sql
GRANT USAGE ON SCHEMA public TO vinhdq;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vinhdq;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO vinhdq;
```

Làm trên từng database nghiệp vụ (`anomaly`, `vms_db`, `its`, …).
- Vẫn bắt buộc SQL Validator trong code.
- Chỉ `SELECT` / `WITH`.
- Connection timeout, statement timeout, giới hạn số dòng.
- Không cho Agent chạy `psql` / shell.
