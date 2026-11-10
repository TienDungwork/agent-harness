# v18 Design — IAM RBAC + domain/geo scope + retrieval rename

**Trạng thái:** Approved (plan Cursor 2026-11-10)  
**Nguồn:** `TAI_LIEU_TICH_HOP_CHATBOT_PHAN_QUYEN_VA_DB.md` §2–§4

## Goal

Mỗi bộ phận (`dashboard_role_group`) chỉ hỏi/đáp domain được phép; SQL luôn lọc org (+ site/area/zone/device khi IAM scope hẹp); API gọi thật `GET /api/v1/auth/me`.

### Enforcement (A + B)

- **A (chính):** allowlist bảng theo role → `retrieve_schema` lọc bảng; `validate_sql` giao allowlist RBAC với catalog.
- **Keyword:** lớp phụ early-deny ở orchestrator (không thay A).
- **B:** `apply_access_scope` ép org (+ geo nếu catalog có cột). Catalog event dong hiện thiếu site/area/zone → geo chưa hiệu lực đến khi bổ sung cột.
- **C:** VMS upstream grounded — ngoài scope code dong hiện tại.

## Auth flow

1. FE gửi `Authorization: Bearer` + `X-Organization-Id` (org HP = **103**).
2. Dong → IAM B2B `GET {IAM_BASE_URL}/api/v1/auth/me` (prod `:21601`, staging `:18641` — không qua CORS FE).
3. Resolve role (giống VMS): `is_system_admin` / `is_organization_admin` → BOARD; else `role_code` / `roles[]`; else `role_details[].permissions.dashboard_role_group` (`security`|`environment`|`operations`|`leadership`). **Top-level `permissions` không có `dashboard_role_group`** (IAM merge bỏ key này).
4. `effective_org`; org ngoài `allowed_organization_ids` → **403** (test: header `106`).
5. Domain guard + `apply_access_scope`; docs filter theo domain.

`IAM_REQUIRED=false` (mặc định): bypass `BOARD_DIRECTOR` + `DB_ORGANIZATION_ID` (eval/local).

Accounts thử: `hp_anninh` / `hp_moitruong` / `hp_vanhanh` / `hp_banlanhdao` / `hp_orgadmin` (password qua VMS/Keycloak). Domain web: `geleximco.atin.vn`.

## Role matrix (dong catalogs)

| role_group | Domains |
|---|---|
| `BOARD_DIRECTOR` | all |
| `SECURITY_DEPT` | traffic, security_events, fire_smoke, face, camera, docs_security |
| `ENVIRONMENT_DEPT` | iot_env, energy, water, lighting, docs_env |
| `OPERATIONS_DEPT` | camera, assets, maintenance, lighting, energy, water, docs_ops (không face) |

Domain → tables: `plate_*`→traffic; `zone_*`→security_events; `fire_smoke_*`→fire_smoke; `smf_*`/`view_face_*`→face; `anomaly_*`→security_events; camera registry/docs→camera/docs_*.

## Rename / layout

- Team graph: `agents/knowledge/` (như `analytics/`) + `docs_agent` mỏng
- Corpus YAML: `agents/knowledge/retrieval/` (`loader` / `retrieval` / `answer`)
- Giữ node ids `retrieve_docs` / `answer_from_docs` / `knowledge_team`

## AC-12

- SECURITY hỏi cháy/xe → OK; hỏi AQI/điện → deny quyền (không SQL domain cấm).
- Org header không allowed → 403.
- SQL sau validate có org (+ geo khi scope hẹp và cột tồn tại).
- `IAM_REQUIRED=false` golden/eval không gãy.
- Không còn import `src.domain.knowledge` / `agents.knowledge`.
