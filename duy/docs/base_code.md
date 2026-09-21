# Local AI Agent — Tổ chức code

Tài liệu này mô tả **cách tổ chức source** cho project `duy`. Mục tiêu và phase: [`muc-tieu.md`](./muc-tieu.md). Kết nối DB: [`ket-noi-db.md`](./ket-noi-db.md). Tiến độ: [`tien-do.md`](./tien-do.md).

Nguyên tắc: **LangGraph điều phối pipeline cố định. Local LLM sinh SQL. Validator không được bypass. Tool/Service mới được chạm Postgres.**

MVP **không** dùng ReAct generic (LLM tự chọn tool). MCP, Analytics, Chart, Camera/VMS thêm sau khi hỏi đáp DB ổn.

---

## 1. Mục tiêu tổ chức

* Hỏi đáp PostgreSQL bằng tiếng Việt theo luồng bắt buộc.
* Nhiều database trên một host (`.200:18644`) — không hard-code một `DB_NAME`.
* Chỉ `SELECT` / `WITH`; user Postgres đã read-only + validator trong code.
* Tách graph / LLM / tool / service.
* Thêm capability sau này mà không viết lại agent core.

Không làm trong cây MVP: Camera, VMS, File, Report, MCP server, Analytics/Chart.

---

## 2. Kiến trúc MVP

```text
                         User
                           |
                           v
                    LangGraph pipeline
                           |
                           v
                      Local LLM
              Ollama · qwen3-16k-nothink (8B)
                           |
                           v
                    PostgreSQL tools
                           |
                           v
                    SQL Validator
                           |
                           v
                 192.168.1.200:18644
                           |
                           v
              anomaly | its | vms_db | ...
```

Luồng bắt buộc (không optional tool):

```text
Question
    v
retrieve_schema     (catalog + schema, chỉ bảng liên quan)
    v
generate_sql        (Local LLM)
    v
validate_sql        (PASS / REJECT)
    |                    |
    | REJECT             | PASS
    v                    v
repair_sql           execute_sql
 (giới hạn số lần)        |
    |                    v
    +---- fail ---->   respond
```

LLM **không** gọi `query` trước khi node `validate_sql` PASS. `execute_sql` / `query_service` vẫn gọi validator lần nữa (hai lớp).

---

## 3. Cây thư mục MVP

Workspace: `/home/atin/duy` (package Python: `agent`).

```text
duy/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .gitignore
│
├── src/
│   └── agent/
│       ├── __init__.py
│       ├── main.py
│       │
│       ├── config/
│       │   ├── settings.py
│       │   └── logging.py
│       │
│       ├── graph/
│       │   ├── graph.py
│       │   ├── state.py
│       │   └── nodes/
│       │       ├── retrieve_schema.py
│       │       ├── generate_sql.py
│       │       ├── validate_sql.py
│       │       ├── repair_sql.py
│       │       ├── execute_sql.py
│       │       └── respond.py
│       │
│       ├── llm/
│       │   └── provider.py
│       │
│       ├── catalog/
│       │   ├── datasets.yaml
│       │   └── retrieval.py
│       │
│       ├── tools/
│       │   └── postgres/
│       │       ├── schema.py
│       │       ├── query.py
│       │       └── validator.py
│       │
│       └── services/
│           ├── connection.py
│           ├── schema_service.py
│           └── query_service.py
│
├── prompts/
│   └── sql_agent.md
│
├── tests/
│   ├── unit/
│   │   ├── test_sql_validator.py
│   │   ├── test_schema_retrieval.py
│   │   └── test_connection_settings.py
│   ├── integration/
│   │   └── test_postgres.py
│   └── questions.json          # evaluation — thêm khi có bộ câu hỏi
│
├── docs/
│   ├── muc-tieu.md
│   ├── tien-do.md
│   ├── ket-noi-db.md
│   └── base_code.md
│
└── outputs/
    └── .gitkeep                # chart PNG sau MVP
```

### Chưa tạo trong MVP (sau này)

```text
src/agent/tools/analytics/
src/agent/tools/chart/
src/agent/mcp/                  # postgres_server.py, camera_server.py, ...
src/agent/tools/camera/
src/agent/tools/vms/
src/agent/tools/report/
docker-compose.yml              # chỉ thêm nếu cần chạy agent thành service
```

---

## 4. Vai trò từng phần

### `graph/`

Điều phối pipeline. **Không** chứa SQL parser, connection string, hay psycopg.

State gợi ý:

```text
question
intent
relevant_datasets      # từ catalog
schema_excerpt
sql
sql_validation         # pass | reject + lý do
repair_count
query_result
answer
error
```

`graph.py` nối node theo thứ tự cố định + cạnh REJECT → `repair_sql` (tối đa N lần) → fail sang `respond`.

### `llm/`

Một chỗ nói chuyện với inference local (OpenAI-compatible: Ollama / vLLM).

Đổi model chỉ sửa `LLM_BASE_URL` / `LLM_MODEL` — không sửa graph.

### `catalog/`

Schema retrieval cho **nhiều database**.

`datasets.yaml` mô tả dataset nghiệp vụ (id, aliases tiếng Việt, database, table, time_column). `retrieval.py` chọn vài card liên quan từ câu hỏi — không dump toàn bộ schema.

Nguồn tham chiếu: `vinhqd/agent/catalog/datasets.yaml` và [`ket-noi-db.md`](./ket-noi-db.md).

### `tools/postgres/`

Capability Postgres mà graph gọi. Mỏng: validate input, gọi service, trả kết quả có giới hạn.

| File | Việc |
|------|------|
| `schema.py` | `get_schema()`, `describe_table()` — đi qua `schema_service` |
| `query.py` | `query(dbname, sql)` — **bắt buộc** gọi validator rồi mới `query_service` |
| `validator.py` | Security boundary: chỉ `SELECT`/`WITH`, cấm multi-statement, block DML/DDL |

### `services/`

Logic dùng lại (tool, test, sau này API).

| File | Việc |
|------|------|
| `connection.py` | Pool, timeout, `connect(dbname=...)`. Tham số rời host/port/user/password/dbname — **không** URL `postgresql://user:pass@host` |
| `schema_service.py` | Đọc information_schema / PK / FK theo `dbname` |
| `query_service.py` | Chỉ execute sau khi validator PASS. Session read-only + statement_timeout + max rows / max size |

**Cấm:** `query_service` hoặc `connection` execute SQL chưa qua `validator.py`.

### `config/settings.py`

Đọc `.env` qua `pydantic-settings`. Không hard-code host/password.

---

## 5. PostgreSQL — hai lớp an toàn

```text
generate_sql
    v
validate_sql  (node graph)     ---- REJECT --> repair_sql
    v PASS
execute_sql
    v
query.py
    v
validator.py  (lần 2, bắt buộc)
    v
query_service.py
    v
connection.py  (readonly session)
    v
192.168.1.200:18644 / <dbname>
```

Cho phép: `SELECT`, `WITH`.

Block: `INSERT` `UPDATE` `DELETE` `DROP` `ALTER` `TRUNCATE` `CREATE` `GRANT` `REVOKE`, multi-statement (`;` giữa câu), shell/`psql`.

Giới hạn: connection timeout, statement timeout, max rows, max result size.

User DB: `vinhdq` (read-only ở tầng Postgres). Vẫn bắt buộc validator trong code.

---

## 6. Configuration

Không commit `.env`. Commit `.env.example`.

Không có `DB_NAME` / `POSTGRES_DB` cố định. `dbname` chọn theo catalog/câu hỏi.

```text
# LLM local — Qwen 8B, đã chốt
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen3-16k-nothink

# Postgres — khớp ket-noi-db.md
DB_HOST=192.168.1.200
DB_PORT=18644
DB_USER=vinhdq
DB_PASSWORD=

# Safety
QUERY_TIMEOUT_SECONDS=10
CONNECT_TIMEOUT_SECONDS=10
MAX_ROWS=200
MAX_RESULT_BYTES=1048576
SQL_REPAIR_MAX=2
```

Chi tiết host/các database nghiệp vụ: [`ket-noi-db.md`](./ket-noi-db.md).

---

## 7. Testing

```text
tests/
├── unit/           # không cần Postgres
├── integration/    # cần .200:18644
└── questions.json  # evaluation sau MVP
```

Unit tối thiểu — `test_sql_validator.py`:

```text
SELECT ...           → PASS
WITH ... SELECT ...  → PASS
INSERT / UPDATE / DELETE / DROP / ALTER / TRUNCATE / CREATE → REJECT
SELECT 1; DROP ...   → REJECT (multi-statement)
```

Integration Phase 3: `SELECT 1` (dbname `postgres` hoặc một DB nghiệp vụ). Chưa cần LLM.

Eval sau MVP: SQL đúng, câu trả lời đúng, chọn đúng DB/bảng, không hallucinate, latency, SQL an toàn.

---

## 8. Dependency

Dùng `uv` (`pyproject.toml` + `uv.lock`).

MVP:

```text
langgraph
langchain-core
langchain-openai          # client OpenAI-compatible cho Ollama/vLLM
pydantic
pydantic-settings
psycopg[binary]
pyyaml
```

Sau MVP: `pandas`, `matplotlib`. MCP extras chỉ khi làm MCP server.

Không thêm `langchain` full nếu chưa cần.

---

## 9. Roadmap gắn cây thư mục

### MVP — tạo các file trong mục 3

1. Local LLM (`llm/provider.py`)
2. LangGraph pipeline (`graph/`)
3. Connection (`services/connection.py` + `.env`)
4. Schema + catalog
5. SQL validator
6. Query + graph `validate_sql` → `execute_sql`
7. NL → SQL → Answer

### Sau MVP — thêm thư mục, không sửa core graph trừ node mới

8. `tools/analytics/`
9. `tools/chart/` → `outputs/*.png`
10. Cải thiện `catalog/retrieval.py`
11. Checkpointer / conversation state
12. `tests/questions.json`

### Cuối — MCP và Operations

13. `mcp/postgres_server.py` bọc **cùng** service hiện có
14. Camera / VMS / Internal API / File / Report MCP
15. Production hardening, auth, audit log

MCP không viết lại logic SQL. Server MCP gọi `validator` + `query_service`.

---

## 10. Design principles

1. **Local-first** — LLM và runtime trên máy; schema/SQL/kết quả không gửi cloud LLM.
2. **Pipeline-first (MVP)** — không ReAct tự do cho câu hỏi DB.
3. **Validator là cửa bắt buộc** — graph node + trong `query.py`.
4. **Multi-DB** — catalog chọn database; connection nhận `dbname`.
5. **Separation** — Graph điều phối, LLM suy luận, Tools mỏng, Services chứa logic, Tests đo.
6. **MVP trước** — không Camera/VMS/Report khi hỏi đáp DB chưa ổn.
7. **Mở rộng được** — thêm tool/MCP mới; không nhét logic vào `graph.py`.

---

## 11. Kiến trúc đích (sau MVP)

```text
                              USER
                                |
                                v
                         LANGGRAPH AGENT
                                |
                         +------+------+
                         |             |
                         v             v
                    LOCAL LLM       STATE
                         |
                         v
              TOOL  (MCP chỉ là vỏ sau này)
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
     PostgreSQL       Analytics       Chart
          |
          v
     .200:18644  (nhiều database)

          Future:
          +-- Camera
          +-- VMS
          +-- Internal API
          +-- File
          +-- Report
```

LangGraph điều phối. Local LLM suy luận. Tool/Service được kiểm soát. Postgres `.200` và hệ thống nội bộ cung cấp dữ liệu.
