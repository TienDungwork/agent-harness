# Agent Canvas — tổng hợp & phân tích (`agent-harness/agent-canvas`)

Tài liệu tham chiếu nội bộ: tổng hợp + phân tích chi tiết (vòng đời agent, bên thứ 3, model đã deploy, phương pháp) từ README, `docs/`, `AGENTS.md`, compose và tùy biến local trong `agent-harness`. Mục đích: hiểu agent harness (Creanova Agent Canvas + VMS) khi đối chiếu với chatbot mỏng `kcn_hungphu_agent`.

### Mục lục

1. [Nguồn monorepo](#1-nguồn-monorepo)
2. [Agent Canvas là gì?](#2-agent-canvas-là-gì)
3. [Ranh giới hệ thống](#3-ranh-giới-hệ-thống)
4. [Kiến trúc runtime (harness local)](#4-kiến-trúc-runtime-harness-local)
5. [Cách agent hoạt động](#5-cách-agent-hoạt-động)
6. [Luồng VMS / analytics](#6-luồng-vms--analytics)
7. [Thao tác với model đã deploy](#7-thao-tác-với-model-đã-deploy)
8. [Thực hiện với bên thứ 3](#8-thực-hiện-với-bên-thứ-3)
9. [Tổng quát các phương pháp đã áp dụng](#9-tổng-quát-các-phương-pháp-đã-áp-dụng)
10. [Stack kỹ thuật (Canvas UI)](#10-stack-kỹ-thuật-canvas-ui)
11. [Chạy nhanh & biến môi trường](#11-chạy-nhanh--biến-môi-trường)
12. [Đối chiếu `kcn_hungphu_agent`](#12-đối-chiếu-kcn_hungphu_agent)
13. [Mental model](#13-mental-model)
14. [Tài liệu gốc & file bằng chứng](#14-tài-liệu-gốc--file-bằng-chứng)
15. [Trạng thái ghi nhận](#15-trạng-thái-ghi-nhận)

---

## 1. Nguồn monorepo

| Path | Vai trò |
|------|---------|
| `../agent-harness/agent-canvas/` | UI + overlay + Docker stack local |
| `../agent-harness/AGENTS.md` | Ghi chú vận hành / tối ưu latency VMS |
| `../agent-harness/services/local-gateway/` | Auth, SSH inventory, rewrite conversation lean |
| `../agent-harness/services/infra-mcp/` | MCP stdio (`vms_query`, SSH tools) |
| `../agent-harness/deploy/clickhouse/` | ClickHouse warehouse + sync |

---

## 2. Agent Canvas là gì?

**Agent Canvas** (package npm `@Creanova/agent-canvas`, ~v1.5.2) là **control center self-hosted** cho coding agent và automation:

- Chat / terminal / files / browser / settings / automations trong một SPA React.
- Không tự thực thi tool — gọi **Creanova Agent Server** (REST + WebSocket) để chạy agent.
- Hỗ trợ nhiều backend (local, Docker, VM, Cloud) và agent ACP (Creanova, Claude Code, Codex, Gemini…).
- Tuỳ chọn **Automation Server** (lịch / webhook → Slack, GitHub…).

Trong harness Atin, bản upstream được **overlay** thành stack KCN: VMS analytics qua ClickHouse + MCP `vms_query`, local auth, gateway path `/agents`.

---

## 3. Ranh giới hệ thống

| Canvas (frontend) làm | Canvas **không** làm |
|-----------------------|----------------------|
| UI hội thoại, settings, backend switch | Thực thi bash/file/browser trực tiếp |
| Gọi Agent Server API / WS | Sandbox / isolation workspace |
| Inject system suffix (`SOUL`, `LOCAL_HARNESS`, runtime services) | Lưu LLM credentials ngoài backend đã cấu hình |
| Render chart VMS (ApexCharts từ marker trong message) | Automation schedule nếu không có automation backend |

**Agent thực sự** chạy trong **Agent Server** (image Hub / SDK), với toolsets mặc định coding + MCP infra (trên lean VMS: coding tools bị strip).

---

## 4. Kiến trúc runtime (harness local)

```text
Browser
  |  http://<host>:18000/agents/  (path gateway)
  |  hoặc :18010/agents/          (canvas trực tiếp)
  v
gateway / local-gateway
  |-- rewrite POST /api/conversations (lean: ít skill, MCP vms_query, LLM từ settings UI)
  |-- auth local (admin / admin123)
  v
agent-canvas container  =  Agent Server + (automation) + Node ingress + UI overlay (./build)
  |
  |-- MCP creanova_infra  -->  vms_query  -->  ClickHouse (vms)
  |-- (optional) SSH / host tools qua MCP
  v
ClickHouse  <---  vms-sync  <---  Postgres nguồn (ITS / fence)
```

Services chính trong `agent-canvas/docker-compose.yml`:

| Service | Chức năng |
|---------|-----------|
| `clickhouse` | Warehouse VMS (`:18123` HTTP loopback) |
| `vms-sync` | Đồng bộ PG → CH |
| `local-gateway` | Auth + lean create + rewrite LLM/MCP |
| `agent-canvas` | Runtime agent + UI bind-mount |
| `gateway` | Path router `:18000` (`/agents`, `/admin`, `/monitoring`) |
| `admin-ui`, `beszel*` | Admin + monitoring host/GPU |
| `canvas-ui-build` | Profile `overlay-build` — build UI vào `./build` |

Image Hub (`ntiendung/agents-harness:…`) chỉ là **runtime**; UI/entrypoint/gateway gắn từ source local.

---

## 5. Cách agent hoạt động

### 5.1 Mô hình tổng quát

Agent Canvas **không** tự chạy tool. Nó là UI + adapter API. “Não” và tool execution nằm ở **Creanova Agent Server**; dữ liệu VMS đi qua **local-gateway → ClickHouse**; SSH/ops đi qua cùng gateway.

```text
User (browser)
    │
    ▼
Agent Canvas UI  ──build payload / WS──►  local-gateway
                                              │ lean rewrite, auth, credits
                                              ▼
                                         Agent Server
                                              │ Agent.step (LLM chọn tool)
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                         FinishTool     MCP creanova_infra   (coding tools
                              │               │               bị strip trên lean)
                              │               ▼
                              │         /api/infra/analytics  → ClickHouse
                              │         /api/infra/*          → SSH / Beszel
                              ▼
                         Events (WS) → UI (text + chart marker)
```

### 5.2 Vòng đời một câu hỏi VMS (Home → trả lời)

1. **Submit Home** (`home-chat-launcher.tsx`)  
   - Ưu tiên **warm conversation** (pre-create trống) → navigate → `sendMessage`.  
   - Không nhồi `initial_message` vào create (tránh chờ MCP + LLM trên cùng request).

2. **Create conversation**  
   - Client: `AgentServerConversationService.createConversation` + `buildStartConversationRequest*` (`agent-server-adapter.ts`).  
   - Inject `mcp_config` (`ensureCreanovaInfraMcpConfig`), `skills: []`, suffix `<LOCAL_HARNESS>`.  
   - **Gateway** (`local-gateway/proxy.py` → `_lean_conversation_create_body`): strip skill catalog, `tools=[]`, chỉ `FinishTool`, MCP nhanh, `autotitle=False`, rewrite LLM từ settings UI (Ollama LAN).

3. **Gửi tin**  
   - REST `sendEvent` hoặc WebSocket (`conversation-websocket-context.tsx`) với `run: true`.

4. **Agent loop** (SDK `LocalConversation.run` → `Agent.step`)  
   - LLM nhận SOUL + harness rules → **tự chọn** tool (thường `vms_query`) + args.  
   - **Không** có router hardcode intent→tool trên loop chính; chỉ hướng dẫn bằng prompt.

5. **MCP** (`services/infra-mcp/mcp_stdio.py`)  
   - Gọi HTTP gateway analytics → query ClickHouse đã curated → JSON có `reply_vi` (+ optional `chart`).

6. **Kết thúc**  
   - **Ưu tiên harness:** patch `patch_vms_reply_vi_finish.py` thấy `reply_vi` → emit MessageEvent (+ chart marker) + `FINISHED` — **bỏ LLM turn 2** (không viết lại câu).  
   - Hoặc model gọi `FinishTool` như upstream.

7. **UI**  
   - Event store / `handle-event-for-ui` → message.  
   - Strip `<!--CREANOVA_VMS_CHART:…-->` → ApexCharts.

### 5.3 Ai chạy gì?

| Thành phần | Trách nhiệm |
|------------|-------------|
| Canvas UI | Chat, settings, warm pool, parse chart, ACP/automation UI |
| local-gateway | Auth, credits, lean create, analytics SQL, SSH bridge |
| Agent Server | Conversation, event bus, spawn MCP, agent loop |
| infra-mcp | Surface tool cho LLM (không chứa SQL business) |
| ClickHouse + vms-sync | Warehouse + đồng bộ từ Postgres nguồn |
| Ollama / cloud LLM | Inference; lean path mặc định Ollama |

---

## 6. Luồng VMS / analytics

### 6.1 Identity & prompt

1. **`config/SOUL.md`** — identity: luôn trả lời tiếng Việt ngắn; chỉ tool `vms_query`; copy `reply_vi` rồi Finish; cấm bịa số / XML `<tool_call>`.
2. **`src/config/local-agent-prompt.ts`** — block `<LOCAL_HARNESS>` (đồng hồ VN + rule action) gắn vào `agent_context.system_message_suffix` khi tạo conversation.
3. Patch trong container (`docker/patch_lean_local_agent.py`, `patch_vms_reply_vi_finish.py`, …) — rút system prompt coding dài, tắt autotitle, kết thúc sớm khi có `reply_vi`, recover tool-call dạng text từ Ollama/Qwen.

### 6.2 Tool dữ liệu

Skill tham chiếu: `packages/extensions/skills/vms-analytics/SKILL.md`.

**Một MCP tool:** `vms_query` với `action=`:

| action | Ý nghĩa |
|--------|---------|
| `count` | Đếm theo ngày / nhiều ngày / tháng (`day`, `days_list`, `month`) |
| `flow` | Ra/vào + loại xe |
| `manufacturer` | Ô tô theo hãng |
| `trace` | Truy vết biển (`q=`) |
| `intrusion` | Peak xâm nhập |

Ngày user (DD/MM) → ISO `YYYY-MM-DD`. Có field `reply_vi` trong JSON → agent **copy nguyên**, không paraphrase.

Chart: MCP trả `chart` → marker `<!--CREANOVA_VMS_CHART:…-->` trong message → UI ApexCharts.

### 6.3 Lean create (tối ưu latency)

Harness **cố ý không** nhồi catalog skill coding (~350KB) vào conversation VMS:

- Create path: `skills: []`, `load_*_skills: false`, thường chỉ MCP `vms_query` (`MCP_VMS_ONLY=1`).
- Warm conversation prefetch trên Home để Enter không chờ MCP handshake lần đầu.
- LLM: Ollama LAN qua `ANALYTICS_LLM_*` / UI profile + gateway rewrite (chi tiết [§7](#7-thao-tác-với-model-đã-deploy)).

---

## 7. Thao tác với model đã deploy

### 7.1 Model đang dùng trên harness (mặc định deploy)

Cấu hình gateway / compose (có thể override bằng `.env`):

| Biến | Giá trị mặc định trong code/compose |
|------|-------------------------------------|
| `ANALYTICS_LLM_BASE_URL` | `http://192.168.1.196:11434/v1` |
| `ANALYTICS_LLM_MODEL` | `qwen3-16k-nothink:latest` |
| `ANALYTICS_LLM_API_KEY` | `ollama` |

- Endpoint: **Ollama** (OpenAI-compatible) trên máy LAN `192.168.1.196:11434`.
- Model tag: **`qwen3-16k-nothink:latest`** (biến thể Qwen3, context dài, tắt “think” để giảm latency / XML lạ).
- Key giả `ollama` — Ollama không bắt API key thật; agent-server/LiteLLM vẫn cần field này.

Nguồn: `services/local-gateway/config.py`, `agent-canvas/docker-compose.yml` (env `local-gateway`).

Đổi model deploy: sửa `.env` của compose → `docker compose up -d local-gateway` (hoặc recreate service), **và** đồng bộ LLM profile trên UI nếu user đang chọn model khác trong Settings.

### 7.2 Hai đường gọi model

```text
(1) Chat Canvas (hot path chính)
  UI LLM profile / settings blob
       → local-gateway _rewrite_llm_from_ui_blob (lean create)
       → Agent Server (LiteLLM / OpenAI-compat client)
       → POST {base}/chat/completions   model=openai/<tag>
       → Ollama LAN

(2) Gateway mini VMS agent (bypass Agent Server — optional API)
  ANALYTICS_LLM_* cố định
       → infra/vms_agent.py httpx
       → POST {base}/chat/completions   model=<tag>  (+ tools count_vehicles)
       → Ollama LAN → tool → ClickHouse → reply_vi
```

Đường (1) dùng khi user chat trên `/agents`.  
Đường (2) dùng API analytics kiểu KCN (`/api/infra/analytics/...` stream agent) — cùng Ollama deploy, không qua MCP/Canvas loop.

Còn path **không gọi LLM**: `ask_vehicle_count` (regex/NL parse → CH) — sub-second.

### 7.3 Cách Canvas “bắt” đúng model deploy (đường 1)

1. **User chọn / lưu LLM profile** trong Settings (`llm-settings`, hooks `use-llm-profiles` / `use-switch-llm-profile`). Blob settings (per-user) chứa `agent_settings.llm`: `model`, `base_url`, `api_key`.

2. **Khi tạo conversation**, gateway `_rewrite_llm_from_ui_blob` (`proxy.py`):
   - Ưu tiên `base_url` / `model` từ UI blob nếu là **fast local** (có `:11434`, `ollama`, hoặc host RFC1918/localhost).
   - Nếu blob trỏ tunnel/cloud (vd. trycloudflare) hoặc không local → **ép về** `ANALYTICS_LLM_*` (model deploy chuẩn).
   - `api_key` redact (`**********`) hoặc Fernet hỏng trên LAN → thay bằng plaintext `ollama`.
   - Model không có prefix provider → gắn `openai/<model>` để LiteLLM/agent-server route đúng OpenAI-compatible client tới Ollama.

3. **Named `agent_profile_id`** bị demote lean: bỏ profile coding, lấy LLM từ UI blob + rewrite như trên (`secrets_encrypted=False` khi key plaintext).

4. **Agent Server** gọi completion với native tool calling (MCP tools + `FinishTool`). Sau tool analytics, patch `reply_vi` thường **không** gọi model lần 2 để viết câu trả lời.

5. **Đổi model trên UI** → `discardWarmLocalConversation()` (`use-switch-llm-profile`, warm prefetch) — warm slot cũ gắn LLM cũ bị hủy, create mới lấy profile mới.

### 7.4 Cách gateway gọi trực tiếp model deploy (đường 2)

`infra/vms_agent.py`:

- Đọc `ANALYTICS_LLM_BASE_URL` / `MODEL` / `API_KEY`.
- Bỏ prefix `openai/` nếu có (`_normalize_model`) — Ollama nhận tên tag thuần.
- `POST …/v1/chat/completions` với `tools=[count_vehicles]`, `tool_choice` auto hoặc forced khi câu mang intent đếm xe.
- Tool chạy helper ClickHouse → JSON `reply_vi` → model (hoặc logic stream) copy câu VI.

Không đi Agent Server / MCP / skill catalog.

### 7.5 Hợp đồng gọi completion (thực tế)

| Khía cạnh | Hành vi harness |
|-----------|-----------------|
| Protocol | OpenAI Chat Completions (`/v1/chat/completions`) |
| Tool calling | Native `tools` + FC (Canvas); mini-agent cũng FC |
| Temperature | Mini-agent ~0.2; lean Canvas thường cap output ngắn |
| Prefix model | Canvas/server: `openai/qwen3-16k-nothink:latest`; httpx thẳng Ollama: bỏ `openai/` |
| Fail thường gặp | Blob UI còn key LiteLLM redact + `secrets_encrypted` sai → `AuthenticationError`; tunnel base_url còn trong blob → chậm/lỗi — rewrite ANALYTICS_LLM xử lý |
| Model “think” / XML | Qwen đôi khi in `<tool_call>…` — `patch_vms_reply_vi_finish` recover; tag `nothink` giảm hành vi nghĩ dài |

### 7.6 Model phía `kcn_hungphu_agent`

Chatbot mỏng cấu hình qua `.env` (`LLM_BACKEND=ollama`, `LLM_BASE_URL`, `LLM_MODEL`, `OPENAI_API_KEYS`), gọi `ChatOpenAI` / `bind_tools` — **một đường**, không có gateway rewrite hay dual path Canvas/mini-agent. Có thể trỏ cùng Ollama deploy (`192.168.1.196:11434` + cùng tag) bằng cách điền `.env` cho khớp `ANALYTICS_LLM_*`.

---

## 8. Thực hiện với bên thứ 3

### 8.1 Hot path KCN / VMS (đang dùng)

| Bên thứ 3 | Mục đích | Cách nối |
|-----------|----------|----------|
| **Ollama** (hoặc OpenAI-compatible) | LLM chọn tool / chào | Settings blob → gateway rewrite lúc create |
| **ClickHouse** | Analytics xe / xâm nhập | MCP → gateway `infra/analytics.py` (agent không SQL) |
| **Postgres nguồn** | OLTP camera AI | `vms-sync` → CH; không query trực tiếp từ agent lean |
| **Postgres/SQLite gateway** | User, session, credits, settings | `DATABASE_URL` |
| **Docker Compose** | Runtime stack | `agent-canvas/docker-compose.yml` |
| **SSH hosts** | Ops remote | MCP `infra_run` / UI SSH WS |
| **Beszel** | Monitor host/GPU | Bridge + Admin Host UI |
| **Keycloak** (optional) | Auth doanh nghiệp | `AUTH_BACKEND=keycloak` |

MCP tools tiêu biểu: `vms_query` (lean / `MCP_VMS_ONLY`), cộng các tool VMS/SSH đầy đủ khi không thu hẹp surface.

### 8.2 Upstream / optional (có trong tree, không bắt buộc VMS)

**1. Catalog MCP / integrations** (`packages/extensions/integrations/catalog/` — hàng chục dịch vụ):  
Slack, GitHub, Linear, Notion, Discord, Jira, Datadog, PostHog, Sentry, Neon, Supabase, Stripe, Google Workspace, Microsoft 365, Vercel, Cloudflare, Tavily/Exa/Firecrawl, …

- **Cách dùng:** Settings / Marketplace → thêm vào `mcp_config` của conversation hoặc agent ACP.  
- Agent gọi tool MCP như tool nội bộ; credentials qua LookupSecrets / env.

**2. Automations** (`packages/extensions/automations/catalog/` + Automation Server `/api/automation/v1`):  
Cron / webhook / dispatch → spawn conversation trên Agent Server. Ví dụ: Slack standup, GitHub PR review, Linear triage, Jira→PR, incident retrospective.

- Canvas chỉ **cấu hình & theo dõi**; execution ở automation backend + agent-server.

**3. ACP agents** (Claude Code, Codex, Gemini CLI, …):  
Profile `agent_kind: "acp"` → server spawn subprocess theo Agent-Client Protocol; Canvas merge `ACPToolCallEvent`. MCP vẫn có thể gắn vào session ACP. Patches lean VMS **không** thay loop ACP.

**4. LLM cloud** (OpenAI, Anthropic, Gemini/Vertex, LiteLLM, Creanova Cloud):  
Qua LLM profiles trong settings; lean LAN cố tránh LiteLLM stale trên disk.

**5. Telemetry PostHog** (Canvas OSS):  
Analytics sản phẩm — tách khỏi path trả lời VMS.

**6. Canvas client tool** `canvas_ui_control`:  
Điều khiển UI từ agent — thường tắt trên LLM private/LAN.

### 8.3 Mẫu tích hợp (tóm tắt)

```text
[A] MCP stdio/HTTP     Agent ↔ tool schema ↔ service API     (VMS, Slack MCP, …)
[B] Automation trigger Cron/webhook → Automation API → Agent Server conversation
[C] ACP subprocess     Canvas ↔ Agent Server ↔ Claude/Codex/… (protocol riêng)
[D] Direct REST        Gateway analytics / SSH (MCP hoặc UI gọi, không qua LLM)
[E] Data plane sync    Postgres → vms-sync → ClickHouse (không phải “tool agent”)
```

---

## 9. Tổng quát các phương pháp đã áp dụng

Nhóm theo mục tiêu thiết kế.

### 9.1 Giảm latency / context (LAN Ollama)

| Phương pháp | Ý tưởng |
|-------------|---------|
| **Lean create** | Tạo conversation “gầy”: không skill catalog, không coding toolset, chỉ Finish + MCP cần thiết |
| **Skill stripping** | Client + gateway + `discover_profile_skills→[]` — tránh ~350–480KB SKILL.md |
| **MCP_VMS_ONLY / single `vms_query`** | Ít schema tool → TTFT nhanh hơn |
| **Fast MCP launcher** | `python3 …/mcp_stdio.py` thay `uv run --with` |
| **Warm conversation** | Pre-create để Enter không chờ handshake MCP |
| **Autotitle off** | Bỏ LLM call đặt tiêu đề hội thoại |
| **SOUL ngắn + drop coding system prompt** | `patch_lean_local_agent` khi có `<LOCAL_HARNESS>` |
| **Greeting tool strip** | Lượt chào: tạm `_tools={}` giảm noise MCP |

### 9.2 Độ chính xác số liệu & UX tiếng Việt

| Phương pháp | Ý tưởng |
|-------------|---------|
| **Prompt contracts** | `SOUL.md` + `<LOCAL_HARNESS>`: luôn VI, map `action=`, ngày DD/MM→ISO |
| **Curated analytics API** | SQL nằm gateway; agent chỉ gọi tool tham số hoá |
| **`reply_vi` short-circuit** | Copy câu đã dựng sẵn, không để LLM paraphrase / bịa số |
| **Chart marker** | Server nhúng JSON chart; UI render, không nhờ LLM vẽ |
| **CLOCK trong harness** | Đồng hồ VN mỗi create — giảm bịa năm |

### 9.3 Robustness model nhỏ (Ollama/Qwen)

| Phương pháp | Ý tưởng |
|-------------|---------|
| **Native function calling** | Ép FC; cấm bịa param như `security_risk` |
| **XML tool-call recovery** | Parse `<tool_call>{…}` / `<function=` thành ActionEvent thật |
| **LLM chọn tool, không hardcode intent** | Giữ tính agent; chỉ patch thực thi đúng tên tool model đã nêu |
| **LLM rewrite từ UI blob** | Tránh key LiteLLM redact / sai endpoint khi đổi user |

### 9.4 Vận hành & an toàn vận hành

| Phương pháp | Ý tưởng |
|-------------|---------|
| **Path gateway + local auth** | Một origin `/agents`, login local |
| **Credits / 402** | Kiểm soát tạo/chạy conversation |
| **Docker overlay UI** | Image runtime + bind-mount build; iterate UI không restart agent |
| **Beszel + nvidia** | Quan sát host/GPU cạnh agent |
| **Optional Keycloak** | Auth chuẩn doanh nghiệp |

### 9.5 Bề mặt sản phẩm upstream (không phải hot path VMS)

| Phương pháp | Ý tưởng |
|-------------|---------|
| **Multi-backend switch** | Nhiều Agent Server từ một UI |
| **Integration marketplace** | MCP catalog + secrets |
| **Automations as templates** | Trigger → agent run có skills/integration |
| **ACP bring-your-own-agent** | Claude/Codex/Gemini cạnh Creanova agent |
| **Library build** | Nhúng Canvas vào host app (`build:lib`) |

### 9.6 Phương pháp bên `kcn_hungphu_agent` (để đối chiếu)

| Phương pháp | Ý tưởng |
|-------------|---------|
| **ReAct + ToolNode** | LangGraph vòng agent⇄tools |
| **Function-calling cố định** | Tool Python có schema; không Text-to-SQL tự do (trừ `run_sql_readonly` whitelist) |
| **Dual LLM** | #1 chọn tool; #2 diễn giải (tắt bằng template) |
| **Regex guardrails** | Input scope/injection + output số liệu/PII — không LLM |

---

## 10. Stack kỹ thuật (Canvas UI)

| Lớp | Công nghệ |
|-----|-----------|
| UI | React 19, React Router 7, Vite 8, Tailwind, HeroUI, Zustand, TanStack Query |
| Client API | `@Creanova/typescript-client` (không gọi HTTP thô ở hầu hết service) |
| Extensions | `@Creanova/extensions` (skills/plugins catalog build-time) |
| Realtime | Socket.IO / WS qua Agent Server |
| Chart VMS | ApexCharts (`react-apexcharts`) |
| Node | ≥ 22.12 |
| Package | CLI `agent-canvas`, build app + `build:lib` |

Thư mục nguồn quan trọng:

- `src/api/` — adapter Agent Server, settings, skills, conversation
- `src/components/` — chat, files, settings, backends, automations, charts VMS
- `src/config/` — SOUL inject, LOCAL_HARNESS, creanova_infra MCP
- `src/stores/`, `src/hooks/` — state & React Query
- `bin/`, `scripts/` — launcher dev / static / runtime-services-info
- `packages/extensions/`, `packages/typescript-client/` — vendored deps

---

## 11. Chạy nhanh & biến môi trường

Chi tiết đầy đủ: `agent-harness/agent-canvas/setup.md`.

```bash
cd agent-harness/agent-canvas
cp -n .env.sample .env
# điền CH_PASSWORD (= CH_VMS_PASSWORD), ANALYTICS_LLM_* nếu đổi host model, v.v.
docker compose --profile overlay-build run --rm canvas-ui-build   # lần đầu / sau đổi UI
docker compose up -d --build
```

| URL | Ghi chú |
|-----|---------|
| `http://<IP>:18000/agents/` | Path gateway (khuyến nghị) |
| `http://<IP>:18010/agents/` | Canvas trực tiếp |
| Login local | `admin` / `admin123` |
| ClickHouse | `127.0.0.1:18123` user `vms_ro` |

Đổi UI only (không restart agent): rebuild overlay + hard-refresh — **không** `docker compose restart agent-canvas` trừ khi đổi entrypoint/compose/env.

Upstream thuần (không overlay Atin): `npm i -g @Creanova/agent-canvas && agent-canvas` hoặc Docker image `ghcr.io/Creanova/agent-canvas:…`.

### Biến môi trường UI đáng nhớ

| Biến | Ý nghĩa |
|------|---------|
| `VITE_BACKEND_BASE_URL` | Base Agent Server |
| `VITE_SESSION_API_KEY` | Session auth tuỳ chọn |
| `VITE_WORKING_DIR` | Workspace mặc định khi start conversation |
| `VITE_BASE_PATH` | Subpath SPA (vd. `/agents`, `/canvas`) |
| `VITE_RUNTIME_SERVICES_INFO` | JSON service URLs → suffix `<RUNTIME_SERVICES>` cho agent |
| `VITE_ENABLE_BROWSER_TOOLS` | Tắt BrowserToolSet nếu `false` |
| `VITE_LOCAL_AUTH_ENABLED` | Local login overlay |

### Biến model / analytics (gateway)

| Biến | Ý nghĩa |
|------|---------|
| `ANALYTICS_LLM_BASE_URL` | Ollama (hoặc OpenAI-compat) LAN |
| `ANALYTICS_LLM_MODEL` | Tag model deploy |
| `ANALYTICS_LLM_API_KEY` | Thường `ollama` |
| `CH_URL` / `CH_USER` / `CH_PASSWORD` | ClickHouse read-only |
| `VMS_ORGANIZATION_ID` | Tenant scope (mặc định 106) |

---

## 12. Đối chiếu `kcn_hungphu_agent`

Cùng bài toán nghiệp vụ (thống kê xe / xâm nhập, tiếng Việt), khác kiến trúc:

| | Agent Canvas (harness) | `kcn_hungphu_agent` |
|--|------------------------|---------------------|
| Vai trò | Control plane + coding agent + MCP + CH | 1 FastAPI chatbot chuyên biệt |
| Agent runtime | Creanova Agent Server (multi-tool) | LangGraph ReAct mỏng |
| Orchestration | Agent Server + MCP | LangGraph `agent ⇄ tools → pack` |
| Chọn tool | LLM FC trên MCP schema | LLM `bind_tools` trên Python tools |
| Dữ liệu | ClickHouse (sync từ PG) qua `vms_query` | Postgres trực tiếp (tools SQL cố định) |
| Trả lời số liệu | `reply_vi` short-circuit | Template + LLM #2 tuỳ chọn |
| UI | SPA React đầy đủ | `static/index.html` |
| Guardrail | Prompt/SOUL + lean patches | `src/guardrails.py` regex/code |
| Model | Dual path + gateway rewrite (`ANALYTICS_LLM_*`) | Một đường `.env` (`LLM_*`) |
| Mục tiêu | Self-host engineering + VMS trên cùng stack | MVP nhẹ, 2 LLM call/câu, máy nhỏ |

Dùng tài liệu này khi cần **port hành vi VMS / prompt / action map / cách gọi model** từ Canvas sang agent mỏng, không cần mang theo toàn bộ Agent Server.

---

## 13. Mental model

**Canvas harness = coding-agent platform bị “cắt gầy” thành analytics agent:** LLM (mặc định Ollama `qwen3-16k-nothink` trên LAN) chỉ còn việc chọn `vms_query` đúng tham số; số liệu và câu tiếng Việt do gateway/ClickHouse quyết định; bên thứ 3 phong phú (Slack/GitHub/ACP…) nằm ở lớp sản phẩm optional, không nằm trên đường đếm xe.

---

## 14. Tài liệu gốc & file bằng chứng

### Tài liệu gốc trong `agent-harness/agent-canvas/`

- `README.md` — tổng quan sản phẩm + quickstart
- `docs/architecture.md` — ranh giới & quality gates
- `docs/SELF_HOSTING.md`, `docs/DEVELOPMENT.md`, `docs/ACP_AGENTS.md`
- `setup.md` — dựng máy mới (Beszel, CH, gateway)
- `AGENTS.md` — quy ước dev frontend / telemetry / E2E
- `config/SOUL.md`, `src/config/local-agent-prompt.ts` — hành vi agent VMS

Trong `agent-harness/`: `AGENTS.md` — latency, warm conversation, patch MCP, chart streaming.

### File bằng chứng (điểm vào nhanh)

| Chủ đề | Path |
|--------|------|
| SOUL | `agent-harness/agent-canvas/config/SOUL.md` |
| LOCAL_HARNESS | `…/src/config/local-agent-prompt.ts` |
| MCP inject | `…/src/config/creanova-infra-mcp.ts` |
| Create payload | `…/src/api/agent-server-adapter.ts` |
| Warm Home | `…/src/utils/warm-local-conversation.ts`, `home-chat-launcher.tsx` |
| Lean gateway | `agent-harness/services/local-gateway/proxy.py` |
| MCP stdio | `agent-harness/services/infra-mcp/mcp_stdio.py` |
| reply_vi patch | `agent-harness/agent-canvas/docker/patch_vms_reply_vi_finish.py` |
| Lean agent patch | `…/docker/patch_lean_local_agent.py` |
| Chart UI | `…/src/components/charts/vms/` |
| Model deploy env | `…/docker-compose.yml` (`ANALYTICS_LLM_*`), `local-gateway/config.py` |
| Rewrite LLM lúc create | `local-gateway/proxy.py` (`_rewrite_llm_from_ui_blob`, `_lean_conversation_create_body`) |
| Mini-agent gọi Ollama | `local-gateway/infra/vms_agent.py` |
| Đổi profile / discard warm | `agent-canvas/src/hooks/mutation/use-switch-llm-profile.ts` |
| Ops notes | `agent-harness/AGENTS.md` |
| Chatbot mỏng | `kcn_hungphu_agent/src/agent/{graph,react,tools,answer}.py`, `src/llm.py` |

---

## 15. Trạng thái ghi nhận

- Canvas = port gần trực tiếp frontend Creanova → nói chuyện thẳng `software-agent-sdk` / agent-server.
- Harness Atin đã customize mạnh cho **VMS + ClickHouse + Ollama**, không phải coding agent “vanilla”.
- Public skill catalog bị tắt trên path tạo conversation local VMS để tránh vượt limit context / LiteLLM.
- Model deploy mặc định: `qwen3-16k-nothink:latest` @ `192.168.1.196:11434`.
- Monitoring kèm Beszel; networking Docker pool khuyến nghị `10.240.0.0/16`.

*Cập nhật file này khi thay đổi lớn SOUL / `vms_query` / compose stack / `ANALYTICS_LLM_*` / mô hình `reply_vi` ảnh hưởng hành vi agent KCN.*
