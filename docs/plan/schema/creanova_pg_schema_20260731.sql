-- =============================================================================
-- Creanova - PostgreSQL schema design
-- Ngày: 31/07/2026
-- Target: PostgreSQL 16, database "creanova", host port 54288
-- Kèm theo: docs/plan/plan_add_feature_postgres_infra_ssh_gpu_20260731.md
--
-- File này là THIẾT KẾ tham chiếu. Khi implement, chuyển thành Alembic
-- migrations (0001_core, 0002_conversations, 0003_infra, 0004_metrics)
-- để có version + downgrade. KHÔNG chạy trực tiếp file này lên prod.
--
-- Quy ước:
--   - Mọi timestamp là TIMESTAMPTZ, lưu UTC.
--   - Tiền/credit dùng NUMERIC, KHÔNG dùng float.
--   - Enum biểu diễn bằng VARCHAR + CHECK (dễ migrate hơn native ENUM).
--   - Schema "public" giữ dữ liệu ứng dụng lõi, schema "infra" giữ hạ tầng.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS infra;

-- gen_random_uuid() có sẵn từ PG13 core, không cần pgcrypto.

-- =============================================================================
-- SECTION 1 — CORE: users, credits, ledger
-- Migrate 1:1 từ SQLite hiện tại, có 3 thay đổi kiểu dữ liệu bắt buộc.
-- =============================================================================

CREATE TABLE public.users (
    id              VARCHAR(64)  PRIMARY KEY,
    keycloak_sub    VARCHAR(128) UNIQUE,              -- NULL khi AUTH_BACKEND=local
    username        VARCHAR(128) NOT NULL UNIQUE,
    email           VARCHAR(255),
    password_hash   TEXT,                             -- pbkdf2_sha256$...; NULL khi dùng Keycloak
    is_admin        BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- Một user phải có ít nhất một cách xác thực.
    CONSTRAINT users_auth_present_chk
        CHECK (keycloak_sub IS NOT NULL OR password_hash IS NOT NULL)
);

COMMENT ON TABLE public.users IS 'Tài khoản do admin tạo. Không có self-signup.';

-- Tra cứu case-insensitive khi login mà vẫn giữ nguyên chữ hoa/thường đã nhập.
CREATE UNIQUE INDEX users_username_lower_uidx ON public.users (lower(username));


CREATE TABLE public.credit_accounts (
    user_id       VARCHAR(64)    PRIMARY KEY
                  REFERENCES public.users(id) ON DELETE CASCADE,
    -- THAY ĐỔI so với SQLite: Float -> NUMERIC. Float làm sai số tích luỹ
    -- khi cộng/trừ nhiều lần, không chấp nhận được với số dư.
    balance       NUMERIC(18,4)  NOT NULL DEFAULT 100.0,
    credit_limit  NUMERIC(18,4)  NOT NULL DEFAULT 100.0,
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT now(),

    -- Chốt bất biến ở tầng DB: không bao giờ âm, kể cả khi code có bug.
    CONSTRAINT credit_accounts_balance_nonneg_chk CHECK (balance >= 0)
);


CREATE TABLE public.usage_ledger (
    id               BIGGSERIAL_PLACEHOLDER,
    user_id          VARCHAR(64)   NOT NULL
                     REFERENCES public.users(id) ON DELETE CASCADE,
    conversation_id  VARCHAR(64),
    run_id           VARCHAR(64),
    usage_type       VARCHAR(64)   NOT NULL DEFAULT 'llm_run',
    units            NUMERIC(18,4) NOT NULL DEFAULT 0,
    -- cost > 0 là trừ tiền, cost < 0 là hoàn tiền (usage_type='refund').
    cost             NUMERIC(18,4) NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT usage_ledger_type_chk
        CHECK (usage_type IN ('llm_run', 'conversation', 'refund', 'admin_adjust', 'infra_tool'))
);

CREATE INDEX usage_ledger_user_created_idx
    ON public.usage_ledger (user_id, created_at DESC);

-- QUAN TRỌNG — sửa lỗi tiềm ẩn của code hiện tại:
-- charge_credits() kiểm tra "đã có ledger cho run_id chưa" bằng SELECT rồi mới
-- INSERT. Trên SQLite việc này vô hại vì ghi bị tuần tự hoá, nhưng trên Postgres
-- hai request song song cùng run_id có thể cùng qua được SELECT và trừ tiền 2 lần.
-- Index unique một phần dưới đây biến idempotency thành ràng buộc thật:
-- request thứ hai sẽ nhận unique violation thay vì trừ tiền lần nữa.
CREATE UNIQUE INDEX usage_ledger_run_idem_uidx
    ON public.usage_ledger (user_id, run_id)
    WHERE run_id IS NOT NULL AND usage_type <> 'refund';


-- =============================================================================
-- SECTION 2 — CONVERSATIONS & TOOLS
-- Postgres chỉ giữ INDEX + METADATA. Nội dung hội thoại vẫn do agent-server
-- quản lý bằng file. Không nhân bản nội dung sang đây.
-- =============================================================================

CREATE TABLE public.conversations (
    conversation_id   VARCHAR(64)  PRIMARY KEY,
    user_id           VARCHAR(64)  NOT NULL
                      REFERENCES public.users(id) ON DELETE CASCADE,
    title             VARCHAR(255),
    status            VARCHAR(32)  NOT NULL DEFAULT 'active',
    -- Nguồn tạo: web UI, SDK, hay tool tự động.
    source            VARCHAR(32)  NOT NULL DEFAULT 'web',
    agent_profile     VARCHAR(128),
    llm_model         VARCHAR(128),
    -- Metadata mở rộng (repo, workspace, tag...). Tránh phải ALTER TABLE liên tục.
    metadata          JSONB        NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_activity_at  TIMESTAMPTZ,
    archived_at       TIMESTAMPTZ,

    CONSTRAINT conversations_status_chk
        CHECK (status IN ('active', 'stopped', 'archived', 'error')),
    CONSTRAINT conversations_source_chk
        CHECK (source IN ('web', 'sdk', 'agent', 'import'))
);

CREATE INDEX conversations_user_activity_idx
    ON public.conversations (user_id, COALESCE(last_activity_at, created_at) DESC);

CREATE INDEX conversations_metadata_gin
    ON public.conversations USING gin (metadata jsonb_path_ops);

-- View tương thích ngược: code Milestone 1/2 đang đọc/ghi bảng user_conversations.
-- Đây là simple view trên một bảng nên Postgres tự động cho phép INSERT/UPDATE/DELETE,
-- các cột còn lại của bảng gốc lấy giá trị DEFAULT. Nhờ vậy có thể migrate schema
-- trước, đổi code sau, không phải làm cùng lúc.
CREATE VIEW public.user_conversations AS
    SELECT conversation_id, user_id, title, created_at
    FROM public.conversations;


CREATE TABLE public.conversation_tools (
    id               BIGGSERIAL_PLACEHOLDER,
    conversation_id  VARCHAR(64)  NOT NULL
                     REFERENCES public.conversations(conversation_id) ON DELETE CASCADE,
    -- Denormalize user_id để truy vấn "user X đã dùng tool gì" không phải join.
    user_id          VARCHAR(64)  NOT NULL
                     REFERENCES public.users(id) ON DELETE CASCADE,
    tool_kind        VARCHAR(32)  NOT NULL,
    tool_name        VARCHAR(255) NOT NULL,
    tool_version     VARCHAR(64),
    source           VARCHAR(255),          -- package, git url, hoặc tên MCP server
    enabled          BOOLEAN      NOT NULL DEFAULT TRUE,
    config           JSONB        NOT NULL DEFAULT '{}'::jsonb,
    installed_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_used_at     TIMESTAMPTZ,

    CONSTRAINT conversation_tools_kind_chk
        CHECK (tool_kind IN ('builtin', 'skill', 'mcp', 'plugin', 'microagent')),
    -- Ghi lại tool nhiều lần (mỗi lần start conversation) không được tạo dòng mới.
    -- Dùng làm target cho INSERT ... ON CONFLICT DO UPDATE.
    CONSTRAINT conversation_tools_uniq
        UNIQUE (conversation_id, tool_kind, tool_name)
);

CREATE INDEX conversation_tools_user_idx ON public.conversation_tools (user_id, tool_name);


CREATE TABLE public.user_mcp_servers (
    id          BIGGSERIAL_PLACEHOLDER,
    user_id     VARCHAR(64)  NOT NULL
                REFERENCES public.users(id) ON DELETE CASCADE,
    name        VARCHAR(128) NOT NULL,
    transport   VARCHAR(16)  NOT NULL,
    -- KHÔNG lưu API key trong config. Secret đi qua user_settings_blobs(kind='secrets').
    config      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT user_mcp_servers_transport_chk
        CHECK (transport IN ('stdio', 'sse', 'http')),
    CONSTRAINT user_mcp_servers_uniq UNIQUE (user_id, name)
);


CREATE TABLE public.user_settings_blobs (
    user_id     VARCHAR(64) NOT NULL
                REFERENCES public.users(id) ON DELETE CASCADE,
    kind        VARCHAR(64) NOT NULL,
    -- THAY ĐỔI so với SQLite: TEXT -> JSONB. Cho phép query/patch từng field
    -- thay vì đọc-parse-ghi cả blob.
    payload     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, kind),
    CONSTRAINT user_settings_blobs_kind_chk
        CHECK (kind IN ('settings', 'secrets', 'profiles'))
);


-- =============================================================================
-- SECTION 3 — INFRA: server inventory + credential
-- =============================================================================

CREATE TABLE infra.servers (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(128) NOT NULL UNIQUE,   -- định danh người dùng gõ: "gpu-01"
    hostname          VARCHAR(255) NOT NULL,
    port              INTEGER      NOT NULL DEFAULT 22,
    username          VARCHAR(128) NOT NULL,
    auth_type         VARCHAR(16)  NOT NULL,
    description       TEXT,
    tags              TEXT[]       NOT NULL DEFAULT '{}',

    -- Host key pinning. Lần kết nối đầu ghi lại fingerprint; các lần sau phải khớp,
    -- lệch nghĩa là server cài lại hoặc bị MITM -> chặn và báo admin.
    host_key_fingerprint  VARCHAR(255),
    host_key_verified_at  TIMESTAMPTZ,

    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    -- Trạng thái sức khoẻ cập nhật sau mỗi lần kết nối.
    last_seen_at      TIMESTAMPTZ,
    last_error        TEXT,
    -- Optimistic lock: chặn tình huống admin sửa server trong lúc lệnh đang chạy.
    row_version       INTEGER      NOT NULL DEFAULT 1,

    created_by        VARCHAR(64)  REFERENCES public.users(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT servers_port_chk     CHECK (port BETWEEN 1 AND 65535),
    CONSTRAINT servers_authtype_chk CHECK (auth_type IN ('key', 'password', 'agent')),
    -- Tên server bị nhúng vào lệnh/log, chặn ký tự lạ ngay từ DB.
    CONSTRAINT servers_name_chk     CHECK (name ~ '^[a-z0-9][a-z0-9._-]{0,127}$')
);

CREATE INDEX servers_tags_gin ON infra.servers USING gin (tags);


-- Tách credential ra bảng riêng để REVOKE quyền đọc cho role read-only,
-- và để mọi câu SELECT * trên infra.servers không bao giờ vô tình lộ secret.
CREATE TABLE infra.server_credentials (
    server_id   UUID        PRIMARY KEY
                REFERENCES infra.servers(id) ON DELETE CASCADE,
    -- Fernet token (base64). Plaintext KHÔNG BAO GIỜ chạm tới DB.
    ciphertext  TEXT        NOT NULL,
    -- Định danh key đang dùng, phục vụ xoay key mà không phải nhập lại toàn bộ.
    key_id      VARCHAR(64) NOT NULL DEFAULT 'default',
    -- Passphrase của private key, cũng mã hoá.
    passphrase_ciphertext TEXT,
    updated_by  VARCHAR(64) REFERENCES public.users(id) ON DELETE SET NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE infra.server_credentials IS
    'Chỉ role creanova_app đọc được. Không expose qua bất kỳ API nào.';


CREATE TABLE infra.server_access_grants (
    id          BIGGSERIAL_PLACEHOLDER,
    server_id   UUID        NOT NULL REFERENCES infra.servers(id) ON DELETE CASCADE,
    user_id     VARCHAR(64) NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    -- read    = xem GPU/services
    -- operate = restart/stop service
    permission  VARCHAR(16) NOT NULL DEFAULT 'read',
    granted_by  VARCHAR(64) REFERENCES public.users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ,

    CONSTRAINT server_access_permission_chk CHECK (permission IN ('read', 'operate')),
    CONSTRAINT server_access_uniq UNIQUE (server_id, user_id)
);

CREATE INDEX server_access_user_idx ON infra.server_access_grants (user_id);

-- Hàm kiểm tra quyền dùng chung cho REST API lẫn MCP tool. Đặt ở DB để
-- không có hai bản logic phân quyền lệch nhau giữa hai đường vào.
CREATE FUNCTION infra.has_server_access(
    p_user_id VARCHAR(64),
    p_server_id UUID,
    p_required VARCHAR(16)
) RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$
    SELECT
        -- Admin luôn có toàn quyền.
        EXISTS (SELECT 1 FROM public.users u
                WHERE u.id = p_user_id AND u.is_admin AND u.is_active)
        OR EXISTS (
            SELECT 1
            FROM infra.server_access_grants g
            JOIN infra.servers s ON s.id = g.server_id
            JOIN public.users  u ON u.id = g.user_id
            WHERE g.server_id = p_server_id
              AND g.user_id   = p_user_id
              AND u.is_active
              AND s.is_active
              AND (g.expires_at IS NULL OR g.expires_at > now())
              AND (g.permission = p_required OR g.permission = 'operate')
        );
$$;


-- =============================================================================
-- SECTION 4 — INFRA: GPU & service metrics
-- =============================================================================

CREATE TABLE infra.gpu_metrics (
    id            BIGGSERIAL_PLACEHOLDER,
    server_id     UUID          NOT NULL REFERENCES infra.servers(id) ON DELETE CASCADE,
    gpu_index     SMALLINT      NOT NULL,
    gpu_uuid      VARCHAR(64),                  -- GPU-xxxxxxxx, ổn định qua reboot
    name          VARCHAR(128),                 -- "NVIDIA RTX A6000"
    mem_total_mb  INTEGER,
    mem_used_mb   INTEGER,
    util_gpu_pct  SMALLINT,
    util_mem_pct  SMALLINT,
    temp_c        SMALLINT,
    power_w       NUMERIC(7,2),
    -- Ai đang chiếm GPU: [{"pid":123,"user":"atin","proc":"python","mem_mb":8000}]
    -- Lưu JSONB thay vì bảng con vì luôn đọc/ghi nguyên cụm theo snapshot.
    processes     JSONB         NOT NULL DEFAULT '[]'::jsonb,
    -- Driver trả giá trị lạ thì giữ nguyên raw để debug parser, không làm hỏng request.
    parse_error   TEXT,
    collected_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    collected_by  VARCHAR(64)   REFERENCES public.users(id) ON DELETE SET NULL,

    CONSTRAINT gpu_metrics_util_chk
        CHECK (util_gpu_pct IS NULL OR util_gpu_pct BETWEEN 0 AND 100),
    CONSTRAINT gpu_metrics_mem_chk
        CHECK (mem_used_mb IS NULL OR mem_total_mb IS NULL OR mem_used_mb <= mem_total_mb)
);

-- Truy vấn chủ đạo: "snapshot mới nhất của server X".
CREATE INDEX gpu_metrics_server_time_idx
    ON infra.gpu_metrics (server_id, collected_at DESC);


CREATE TABLE infra.service_snapshots (
    id            BIGGSERIAL_PLACEHOLDER,
    server_id     UUID         NOT NULL REFERENCES infra.servers(id) ON DELETE CASCADE,
    unit_name     VARCHAR(255) NOT NULL,
    load_state    VARCHAR(32),        -- loaded / not-found / masked
    active_state  VARCHAR(32),        -- active / inactive / failed / activating
    sub_state     VARCHAR(32),        -- running / dead / exited
    description   TEXT,
    since         TIMESTAMPTZ,        -- thời điểm vào trạng thái hiện tại
    collected_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- Chặn injection ngay tại DB: unit name bị ghép vào lệnh systemctl.
    CONSTRAINT service_unit_name_chk
        CHECK (unit_name ~ '^[A-Za-z0-9@:._\\-]+\.(service|socket|timer|target|mount)$')
);

CREATE INDEX service_snapshots_server_time_idx
    ON infra.service_snapshots (server_id, collected_at DESC);


-- Snapshot mới nhất mỗi GPU. Dùng thay cho cache trong process:
-- nếu collected_at còn trong 5 giây thì API trả thẳng, khỏi mở phiên SSH mới.
-- Cách này cũng làm single-flight hoạt động đúng khi chạy nhiều worker.
CREATE VIEW infra.gpu_latest AS
    SELECT DISTINCT ON (server_id, gpu_index) *
    FROM infra.gpu_metrics
    ORDER BY server_id, gpu_index, collected_at DESC;

CREATE VIEW infra.service_latest AS
    SELECT DISTINCT ON (server_id, unit_name) *
    FROM infra.service_snapshots
    ORDER BY server_id, unit_name, collected_at DESC;


-- =============================================================================
-- SECTION 5 — AUDIT
-- =============================================================================

CREATE TABLE infra.audit_log (
    id                BIGGSERIAL_PLACEHOLDER,
    actor_user_id     VARCHAR(64)  REFERENCES public.users(id) ON DELETE SET NULL,
    -- Phân biệt người bấm nút và agent tự gọi tool.
    actor_kind        VARCHAR(16)  NOT NULL DEFAULT 'user',
    conversation_id   VARCHAR(64),          -- có giá trị khi actor_kind='agent'
    server_id         UUID         REFERENCES infra.servers(id) ON DELETE SET NULL,
    -- Giữ tên server dạng text: server bị xoá vẫn đọc được lịch sử.
    server_name       VARCHAR(128),
    action            VARCHAR(64)  NOT NULL,
    command_id        VARCHAR(64),          -- khoá trong whitelist ở infra/commands.py
    command_rendered  TEXT,                 -- lệnh thật đã chạy, phục vụ điều tra
    exit_code         INTEGER,
    success           BOOLEAN      NOT NULL,
    duration_ms       INTEGER,
    error_excerpt     TEXT,                 -- cắt ngắn, tuyệt đối không chứa secret
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT audit_actor_kind_chk CHECK (actor_kind IN ('user', 'agent', 'system')),
    CONSTRAINT audit_action_chk CHECK (action IN (
        'server.create', 'server.update', 'server.delete',
        'credential.set', 'connection.test',
        'gpu.query', 'service.list', 'service.restart', 'service.stop',
        'command.run', 'access.denied'
    ))
);

CREATE INDEX audit_log_created_idx ON infra.audit_log (created_at DESC);
CREATE INDEX audit_log_server_idx  ON infra.audit_log (server_id, created_at DESC);
CREATE INDEX audit_log_actor_idx   ON infra.audit_log (actor_user_id, created_at DESC);

-- Audit là append-only. Chặn sửa/xoá ngay ở DB để log không bị dọn dẹp sau sự cố.
CREATE RULE audit_log_no_update AS ON UPDATE TO infra.audit_log DO INSTEAD NOTHING;
CREATE RULE audit_log_no_delete AS ON DELETE TO infra.audit_log DO INSTEAD NOTHING;


-- =============================================================================
-- SECTION 6 — Khoá chống đua và dọn dữ liệu
-- =============================================================================

-- Chặn hai phiên cùng restart một unit trên cùng một server.
-- Advisory lock ở mức transaction: tự nhả khi commit/rollback, không để lại
-- khoá treo nếu tiến trình chết giữa chừng.
CREATE FUNCTION infra.try_lock_service(p_server_id UUID, p_unit TEXT)
RETURNS BOOLEAN
LANGUAGE sql AS $$
    SELECT pg_try_advisory_xact_lock(
        hashtext(p_server_id::text || '/' || p_unit)::bigint
    );
$$;

-- Metric sinh liên tục, phải có đường dọn. Gọi định kỳ bằng cron ngoài,
-- chưa cần pg_cron ở quy mô hiện tại.
CREATE FUNCTION infra.prune_metrics(p_retain INTERVAL DEFAULT '30 days')
RETURNS TABLE (gpu_deleted BIGINT, service_deleted BIGINT)
LANGUAGE plpgsql AS $$
DECLARE
    v_gpu BIGINT;
    v_svc BIGINT;
BEGIN
    DELETE FROM infra.gpu_metrics WHERE collected_at < now() - p_retain;
    GET DIAGNOSTICS v_gpu = ROW_COUNT;

    DELETE FROM infra.service_snapshots WHERE collected_at < now() - p_retain;
    GET DIAGNOSTICS v_svc = ROW_COUNT;

    RETURN QUERY SELECT v_gpu, v_svc;
END;
$$;


-- =============================================================================
-- SECTION 7 — Roles và quyền
-- =============================================================================

-- creanova_app: role của gateway, đọc/ghi tất cả.
-- creanova_ro : role báo cáo/debug, KHÔNG đọc được credential.

CREATE ROLE creanova_app LOGIN PASSWORD 'changeme_in_env';
CREATE ROLE creanova_ro  LOGIN PASSWORD 'changeme_in_env';

GRANT USAGE ON SCHEMA public, infra TO creanova_app, creanova_ro;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public, infra TO creanova_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public, infra TO creanova_app;

GRANT SELECT ON ALL TABLES IN SCHEMA public, infra TO creanova_ro;
-- Kiểm soát quan trọng nhất của thiết kế này:
REVOKE ALL ON infra.server_credentials FROM creanova_ro;
REVOKE ALL ON public.users FROM creanova_ro;   -- chứa password_hash

ALTER DEFAULT PRIVILEGES IN SCHEMA public, infra
    GRANT SELECT ON TABLES TO creanova_ro;


-- =============================================================================
-- SECTION 8 — Truy vấn tham chiếu
-- =============================================================================

-- 8.1 Trừ credit một lần duy nhất cho mỗi run (thay cho SELECT-rồi-INSERT).
--     Nếu run_id đã tồn tại, ON CONFLICT làm nó thành no-op và không trừ tiền.
--
-- WITH ins AS (
--     INSERT INTO public.usage_ledger (user_id, conversation_id, run_id, usage_type, units, cost)
--     VALUES ($1, $2, $3, 'llm_run', 1, $4)
--     ON CONFLICT (user_id, run_id) WHERE run_id IS NOT NULL AND usage_type <> 'refund'
--     DO NOTHING
--     RETURNING id, cost
-- )
-- UPDATE public.credit_accounts a
--    SET balance = a.balance - (SELECT cost FROM ins),
--        updated_at = now()
--  WHERE a.user_id = $1
--    AND EXISTS (SELECT 1 FROM ins)
--    AND a.balance >= (SELECT cost FROM ins)
-- RETURNING a.balance;
--
-- Không trả về dòng nào = hết credit (CHECK balance >= 0 cũng chặn ở lớp cuối).

-- 8.2 Ghi tool đã cài, chạy lại nhiều lần không sinh dòng trùng.
--
-- INSERT INTO public.conversation_tools
--        (conversation_id, user_id, tool_kind, tool_name, tool_version, source, config)
-- VALUES ($1, $2, $3, $4, $5, $6, $7)
-- ON CONFLICT (conversation_id, tool_kind, tool_name)
-- DO UPDATE SET enabled = TRUE,
--               tool_version = EXCLUDED.tool_version,
--               config = EXCLUDED.config,
--               last_used_at = now();

-- 8.3 GPU còn trống nhiều nhất trong số server user được phép xem.
--
-- SELECT s.name, g.gpu_index, g.name AS gpu,
--        g.mem_total_mb - g.mem_used_mb AS free_mb,
--        g.util_gpu_pct, g.collected_at
--   FROM infra.gpu_latest g
--   JOIN infra.servers s ON s.id = g.server_id
--  WHERE infra.has_server_access($1, s.id, 'read')
--    AND g.collected_at > now() - interval '5 minutes'
--  ORDER BY free_mb DESC;

-- 8.4 Kiểm tra cache 5 giây trước khi mở phiên SSH mới.
--
-- SELECT * FROM infra.gpu_latest
--  WHERE server_id = $1 AND collected_at > now() - interval '5 seconds';


-- =============================================================================
-- GHI CHÚ MIGRATION SQLite -> PostgreSQL
-- =============================================================================
-- 1. BIGGSERIAL_PLACEHOLDER ở trên viết đầy đủ là:
--        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
--    (giữ placeholder để không ai copy-paste chạy thẳng file thiết kế này).
-- 2. balance/credit_limit/units/cost: REAL -> NUMERIC(18,4).
--    Script migrate phải làm tròn 4 chữ số và đối chiếu tổng trước/sau.
-- 3. user_settings_blobs.payload: TEXT -> JSONB, cần json.loads khi copy.
--    Dòng nào không parse được thì bỏ qua và log, không làm hỏng cả lần chạy.
-- 4. users.keycloak_sub NULL không vi phạm UNIQUE trong Postgres, giữ nguyên.
-- 5. user_conversations trong SQLite đổ vào bảng conversations mới;
--    status mặc định 'active', source mặc định 'import'.
-- 6. Chạy migrate hai lần phải cho cùng kết quả: dùng
--    INSERT ... ON CONFLICT DO NOTHING cho mọi bảng.
-- 7. Kiểm tra sau migrate:
--      SELECT count(*) FROM users;
--      SELECT sum(balance) FROM credit_accounts;
--      SELECT count(*) FROM conversations;
--    phải khớp số liệu đếm từ file SQLite cũ.
