# Local AI Agent — Mục tiêu & Lộ trình

Dự án xây dựng một **Local AI Agent dựa trên LangGraph**, trong đó toàn bộ Agent Runtime, LLM inference, Tools/MCP và dữ liệu được xử lý trong môi trường local/private.

Mục tiêu ban đầu là xây dựng Agent có khả năng **hỏi đáp dữ liệu PostgreSQL bằng ngôn ngữ tự nhiên**, sau đó mở rộng thành **AI Data / Operations Agent** có khả năng phân tích dữ liệu, tạo biểu đồ và tương tác với các hệ thống nội bộ như Camera/VMS, Internal API và Report.

Tiến độ: [`tien-do.md`](./tien-do.md). Kết nối PostgreSQL: [`ket-noi-db.md`](./ket-noi-db.md). Tổ chức code: [`base_code.md`](./base_code.md).

---

## 1. Mục tiêu chính

| #  | Mục tiêu                   | Mô tả                                                                                                                          |
| -- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 1  | Local AI Agent             | Xây dựng Agent bằng **LangGraph**, chạy Agent Runtime hoàn toàn local.                                                         |
| 2  | Local LLM                  | Sử dụng LLM chạy local thông qua **vLLM / Ollama hoặc inference server tương đương**, không phụ thuộc API LLM bên ngoài.       |
| 3  | Hỏi đáp PostgreSQL         | Cho phép người dùng đặt câu hỏi bằng tiếng Việt; Agent tự xác định schema, sinh SQL và trả lời dựa trên dữ liệu thực tế.       |
| 4  | An toàn với Production DB  | Chỉ cho phép `SELECT`, sử dụng DB account read-only, SQL validator, timeout và giới hạn kết quả.                               |
| 5  | Phân tích dữ liệu          | Chuyển dữ liệu SQL thành DataFrame và thực hiện grouping, aggregation, statistics, filtering, sorting và time-series analysis. |
| 6  | Vẽ biểu đồ                 | Agent có thể tạo bar chart, line chart, time-series và Top-N chart từ dữ liệu PostgreSQL.                                      |
| 7  | Tool / MCP Architecture    | Xây dựng hệ thống Tool/MCP có thể mở rộng để Agent tương tác với PostgreSQL, Analytics, Camera/VMS và Internal API.            |
| 8  | AI Operations Agent        | Mở rộng từ Data Agent thành Agent có khả năng truy vấn và thực hiện các tác vụ đọc dữ liệu từ hệ thống AI/VMS nội bộ.          |
| 9  | Agent Architecture thực tế | Tìm hiểu và triển khai Agent loop, state, context, tool calling, memory, permission, logging và evaluation.                    |
| 10 | Privacy / Self-hosted      | Không gửi dữ liệu PostgreSQL, camera, event hoặc thông tin hệ thống nội bộ tới LLM/API bên ngoài.                              |

---

## 2. Kiến trúc mục tiêu

```text
                         User
                           ↓
                    LangGraph Agent
                           ↓
                    Local LLM Server
                     (vLLM / Ollama)
                           ↓
                 ┌─────────┴─────────┐
                 ↓                   ↓
            Agent Tools             MCP
                 ↓                   ↓
        ┌────────┼────────┐   ┌──────┼──────┐
        ↓        ↓        ↓   ↓      ↓      ↓
       DB     Analytics  Chart  Camera  VMS  API
        ↓
 PostgreSQL
```

Tất cả các thành phần chính được triển khai trong môi trường local/private:

```text
LangGraph
    ↓
Local LLM
    ↓
Local Tools / MCP
    ↓
Internal Services / PostgreSQL
```

Không sử dụng OpenAI, Anthropic, OpenRouter hoặc cloud LLM cho inference của Agent.

---

## 3. Luồng hỏi đáp PostgreSQL

MVP tập trung vào luồng:

```text
User Question
      ↓
LangGraph Agent
      ↓
Schema Retrieval
      ↓
LLM sinh SQL
      ↓
SQL Validator
      ↓
PASS ───────→ PostgreSQL
                  ↓
             Query Result
                  ↓
              LLM Analyze
                  ↓
                Answer
```

Nếu SQL không hợp lệ:

```text
SQL
 ↓
Validator
 ↓
REJECT
 ↓
Agent nhận lỗi
 ↓
Sửa SQL hoặc thông báo lỗi
```

LLM **không được phép bypass SQL Validator**.

---

## 4. Nguyên tắc Local

### Local LLM

LLM được chạy trực tiếp trên máy chủ có GPU:

```text
LangGraph
    ↓
localhost:11434
    ↓
Ollama
    ↓
qwen3-16k-nothink  (Qwen 8B)
```

Đã chốt: **Qwen 8B**, tag `qwen3-16k-nothink` (tắt thinking, ctx 16k). Không dùng `qwen3:4b` hay bản `qwen3:8b` còn thinking. vLLM để dành nếu sau này cần serving khác.

### Local Agent Runtime

LangGraph, Python tools và MCP servers chạy local.

### Local Data

PostgreSQL và các hệ thống nội bộ được truy cập trực tiếp trong private network.

### Không gửi dữ liệu ra ngoài

Các dữ liệu như:

* Database schema
* SQL
* Camera information
* Event data
* Vehicle data
* VMS information
* Internal API response

không được gửi tới cloud LLM.

---

## 5. Phạm vi

### 5.1 In scope

* LangGraph Agent.
* Local LLM.
* Local inference server.
* PostgreSQL MCP / Tool.
* SQL safety layer.
* PostgreSQL schema retrieval.
* Natural-language → SQL.
* Read-only database access.
* Pandas data analysis.
* Matplotlib chart generation.
* Agent state và context.
* Tool calling.
* Logging.
* Evaluation.
* Camera/VMS/Internal API tools sau MVP.

### 5.2 Out of scope giai đoạn đầu

* Cloud LLM.
* OpenRouter / OpenAI / Anthropic inference.
* Agent tự chạy shell.
* Agent tự chạy `psql`.
* `INSERT`.
* `UPDATE`.
* `DELETE`.
* `DROP`.
* `ALTER`.
* `TRUNCATE`.
* Tự động thay đổi hệ thống production.
* Camera/VMS/Report MCP trước khi PostgreSQL Agent ổn định.

---

# 6. Các Phase

## Phase 1 — Dựng Local LLM

Mục tiêu:

```text
Python → Local LLM → Answer
```

Cần hoàn thành:

* Cài inference server.
* Load local model.
* Test inference.
* Test Vietnamese question/answer.
* Kiểm tra GPU memory và tốc độ inference.
* Test OpenAI-compatible API nếu inference server hỗ trợ.

Kết quả:

```text
User
 ↓
Local LLM
 ↓
Answer
```

---

## Phase 2 — Dựng LangGraph Agent

Mục tiêu:

```text
User
 ↓
LangGraph
 ↓
Local LLM
 ↓
Answer
```

Cần làm:

* LangGraph state.
* Agent node.
* LLM node.
* Basic agent loop.
* Tool calling.
* Error handling.

Kết quả:

Agent có thể nhận câu hỏi và quyết định khi nào cần sử dụng Tool.

---

## Phase 3 — PostgreSQL Connection

Tạo project riêng cho Data Agent.

Nguồn DB đã chốt: Postgres production **`192.168.1.200:18644`**, user read-only `vinhdq`, nhiều database (`anomaly`, `smart_face`, `its`, `vms_db`, …). Chi tiết: [`ket-noi-db.md`](./ket-noi-db.md).

Cần làm:

* `.env` (`DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` — password không commit).
* PostgreSQL driver.
* Connection pool.
* Connection timeout.
* Test `SELECT 1`.
* User `vinhdq` đã read-only — không cần tạo user mới trừ khi đổi account.

Kết quả:

```text
Python
 ↓
192.168.1.200:18644
 ↓
SELECT
```

---

## Phase 4 — PostgreSQL Tool / MCP

Xây dựng các tool đầu tiên:

### `get_schema()`

Trả về:

* Database/schema.
* Tables.
* Columns.
* Data types.
* Primary keys.
* Foreign keys.

### `describe_table()`

Trả về thông tin chi tiết của một table.

### `query()`

Thực thi SQL sau khi đi qua SQL Validator.

Kiến trúc:

```text
LangGraph
    ↓
PostgreSQL Tool / MCP
    ↓
SQL Validator
    ↓
PostgreSQL
```

---

## Phase 5 — SQL Safety

Đây là layer bắt buộc trước khi Agent truy cập production DB.

### Cho phép

```sql
SELECT ...
```

### Block

```text
INSERT
UPDATE
DELETE
DROP
ALTER
TRUNCATE
CREATE
GRANT
REVOKE
```

### Giới hạn

* Query timeout.
* Connection timeout.
* Maximum rows.
* Maximum result size.
* Maximum execution time.
* Không cho multi-statement.
* Không cho Agent truy cập shell/`psql`.

Kiến trúc:

```text
LLM
 ↓
Generated SQL
 ↓
SQL Validator
 ├── REJECT
 └── PASS
       ↓
   PostgreSQL
```

---

## Phase 6 — LangGraph + PostgreSQL Agent

Đây là **MVP chính**.

Agent phải thực hiện được:

```text
Question
   ↓
Understand intent
   ↓
Get schema
   ↓
Generate SQL
   ↓
Validate SQL
   ↓
Execute query
   ↓
Understand result
   ↓
Answer
```

Bộ test tối thiểu:

1. Có bao nhiêu camera?
2. Có bao nhiêu camera đang hoạt động?
3. Top 10 camera có nhiều event nhất?
4. Có bao nhiêu event trong tháng 8?
5. Camera nào có nhiều event nhất?
6. Có bao nhiêu vehicle event theo từng ngày?
7. Camera nào có nhiều violation nhất?

Kết quả MVP:

> **Có thể hỏi PostgreSQL bằng tiếng Việt và Agent tự truy vấn dữ liệu bằng SQL an toàn.**

---

## Phase 7 — Data Analysis

Thêm Analytics Tool.

```text
PostgreSQL
     ↓
DataFrame
     ↓
Pandas
     ↓
Analysis
```

Chức năng:

* Group by.
* Aggregation.
* Filtering.
* Sorting.
* Statistics.
* Comparison.
* Time-series.
* Top-N.

Ví dụ:

> So sánh số lượng event của từng camera trong tháng 8.

---

## Phase 8 — Chart Agent

Thêm Chart Tool.

Các tool ban đầu:

```text
create_bar_chart()
create_line_chart()
create_time_series_chart()
```

Luồng:

```text
Question
 ↓
LangGraph
 ↓
SQL
 ↓
PostgreSQL
 ↓
DataFrame
 ↓
Matplotlib
 ↓
PNG
```

Ví dụ:

> Vẽ số lượng event theo từng ngày trong tháng 8.

---

## Phase 9 — Schema Retrieval

Khi database lớn, không gửi toàn bộ schema cho LLM.

Luồng:

```text
Question
 ↓
Schema Retrieval
 ↓
Relevant Tables
 ↓
LLM
 ↓
SQL
```

Ví dụ:

```text
Question:
Camera nào có nhiều event nhất?

Relevant:
- cameras
- events
```

Mục tiêu:

* Giảm context.
* Giảm token.
* Tăng tốc.
* Tăng SQL accuracy.

---

## Phase 10 — Context & Memory

Sau khi MVP ổn định, thêm:

* Conversation state.
* Context management.
* Schema cache.
* Tool result management.
* Conversation history.
* Memory khi thực sự cần.

Ví dụ:

```text
User:
Cho tôi event tháng 8.

User:
Chỉ lấy camera Hà Nội.

User:
Vẽ biểu đồ.
```

Agent phải hiểu rằng các câu hỏi sau đang tiếp tục context trước đó.

---

## Phase 11 — Evaluation

Tạo:

```text
tests/
    questions.json
```

Mỗi câu hỏi có expected result hoặc expected behavior.

Đánh giá:

* SQL đúng.
* Answer đúng.
* Chọn đúng bảng.
* Chọn đúng tool.
* Không hallucinate.
* SQL an toàn.
* Query latency.
* Tool latency.
* Error handling.
* Token/context usage.

Mục tiêu không chỉ là:

> "Agent trả lời được."

Mà phải đo được:

> "Agent trả lời đúng bao nhiêu phần trăm?"

---

## Phase 12 — Mở rộng thành AI Operations Agent

Sau khi PostgreSQL Agent ổn định, mở rộng Tool/MCP:

```text
                    LangGraph
                        │
              Local LLM + Tools
                        │
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
 PostgreSQL          Camera/VMS      Internal API
    MCP                 MCP               MCP
        │               │               │
        ↓               ↓               ↓
       DB             Cameras        AI Services
```

Các tool có thể gồm:

```text
get_camera_status()
get_stream_status()
get_camera_events()
get_vehicle_events()
get_water_level()
get_violation_events()
```

---

## Phase 13 — Report Agent

Sau khi Data + Chart ổn định:

```text
PostgreSQL
     ↓
Analytics
     ↓
Charts
     ↓
Report
     ↓
PDF / Excel / Markdown
```

Ví dụ:

> Tạo báo cáo tình trạng camera tuần này.

Agent có thể:

1. Lấy dữ liệu.
2. Phân tích.
3. Tạo biểu đồ.
4. Tổng hợp kết quả.
5. Sinh báo cáo.

---

# 7. Thứ tự ưu tiên

## MVP

```text
1. Local LLM
2. LangGraph
3. PostgreSQL connection
4. PostgreSQL Tool/MCP
5. SQL Validator
6. LangGraph → PostgreSQL
7. Natural Language → SQL → Answer
```

## Sau MVP

```text
8. Pandas
9. Chart
10. Schema Retrieval
11. Context / Memory
12. Evaluation
```

## Cuối cùng

```text
13. Camera MCP
14. VMS MCP
15. Internal API MCP
16. File MCP
17. Report MCP
18. Production hardening
```

---

# 8. Kiến trúc cuối cùng

Mục tiêu cuối cùng:

```text
                         USER
                           │
                           ↓
                    LANGGRAPH AGENT
                           │
                           ↓
                     LOCAL LLM
                    (vLLM / etc.)
                           │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
         PostgreSQL     Analytics      Chart
            MCP           Tool          Tool
              │
              ↓
         PostgreSQL
              
              ┌──────────────────────────┐
              │     Future Tools         │
              │                          │
              │ Camera MCP               │
              │ VMS MCP                  │
              │ Internal API MCP         │
              │ File MCP                 │
              │ Report MCP               │
              └──────────────────────────┘
```

**Nguyên tắc cốt lõi:**

> **LangGraph điều phối Agent. Local LLM suy luận. Tool/MCP cung cấp khả năng hành động. PostgreSQL và các hệ thống nội bộ cung cấp dữ liệu. Toàn bộ hệ thống chạy trong môi trường local/private.**
