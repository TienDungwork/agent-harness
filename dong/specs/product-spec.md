# Product Spec — agent dong v6 (MVP)

**Trạng thái:** v6 in progress — **Phase 1 done** (resource/ layout). Kế thừa v5 (QueryPlan, Docker, golden-30).

## App goal

Trợ lý tiếng Việt cho vận hành VMS KCN Hưng Phú: hỏi số liệu (read-only), hướng dẫn VMS/AIOC, và xem biểu đồ — code ngắn, rõ, chạy production bằng Docker.

MVP v6 thêm: memory (short / long / TTL 5 phút), sidebar session, prompt LLMOps trong `resource/`, multi-agent để cải thiện golden-30, và trace đầy đủ input/output mỗi node.

## Target users

| Ai | Họ làm gì với app |
|----|-------------------|
| Vận hành KCN | Hỏi tiếng Việt; đổi session; xem số liệu / hướng dẫn / biểu đồ — không viết SQL |
| Dev / reviewer | Chạy Docker, xem live graph + Langfuse, chạy eval → `eval/results/golden-30.md` |

## Core user flow

1. Mở UI → chọn hoặc tạo **session** (cột trái).
2. Gõ câu hỏi tiếng Việt (tuỳ chọn: gợi ý domain trong khung chat).
3. Backend: recall memory → guardrail → rewrite → classify → route.
4. Nhánh xử lý:
   - **Số liệu:** QueryPlan → SQL read-only → (tuỳ câu) chart → trả lời
   - **Hướng dẫn:** lấy card từ `resource/docs/` → trả lời
   - **Khó / đa domain:** orchestrator multi-agent ngắn
5. Lưu short-term; có thể store long-term; TTL cache 5 phút nếu trùng câu.
6. UI stream câu trả lời + biểu đồ; live graph / Langfuse hiện **full I/O** từng node.

## Features in scope

- Code sạch, production-only; file tĩnh gom vào `resource/` (prompts, docs, db catalog).
- Prompt management kiểu LLMOps: YAML versioned + `production.txt`; nội dung ngắn, rõ.
- Docker là đường chạy chính; không dùng venv trong quick start.
- Đổi LLM bằng `LLM_BACKEND`: `self_hosted` (gateway 196) ↔ `openai` (keys pattern `llm-engineer-demo/.env`).
- Memory: short-term theo session, long-term theo `user_id`, TTL response cache **300 giây**.
- UI: cột trái = danh sách session; domain chips nằm trong chat.
- Biểu đồ theo câu hỏi: **bar**, **pie** (MVP; line nếu dễ).
- Trace: mỗi graph node ghi đủ input và output (Langfuse + SSE hover).
- Multi-agent MVP để pass các case fail golden-30 (008–011, 015, 017, 023, 024).
- Eval live trên LLM 196 + judge → cập nhật `eval/results/golden-30.md` (target ≥28/30; baseline 22/30).

## Features out of scope

- Venv / local pip là đường chính.
- Ghi DB production, web search, MCP, swarm agent phức tạp.
- Sync prompt lên Langfuse Cloud.
- Backend Ollama.
- Graph editor / dashboard analytics ngoài chat.

## Acceptance criteria

1. `docker compose up --build -d` → healthy; không bắt buộc `.venv`.
2. `LLM_BACKEND=self_hosted` + gateway 196 → `/api/llm/ping` OK.
3. `LLM_BACKEND=openai` + keys theo pattern `llm-engineer-demo` → smoke OK.
4. Prompt chỉ load từ `resource/prompts/`; đổi `production.txt` → đổi hành vi, không sửa code.
5. Langfuse / SSE: hover node thấy **full** input và output.
6. Sidebar: tạo / chuyển session; short-term nhớ trong cùng session.
7. Long-term: nói 1 fact → session mới cùng `user_id` vẫn recall (smoke).
8. TTL: cùng câu trong 5 phút → `cache_hit` (hoặc trả lời identical nhanh hơn).
9. Chart **bar** và **pie** render đúng trên UI.
10. Golden-30 live trên 196: **≥28/30 pass**; file `eval/results/golden-30.md` cập nhật.
11. `pytest -q` xanh offline.

---

## Ghi chú MVP (không mở rộng scope)

| Chủ đề | Quyết định ngắn |
|--------|-----------------|
| Layout UI | `[Sessions] \| [Chat] \| [Live graph]` |
| Memory | Short = checkpointer theo `session_id`; long = vector/in-memory theo `user_id`; TTL = hash(question+route), 300s |
| Prompt bắt buộc | rewrite, classify, plan_query, answer_docs, respond_stat, plan_chart, orchestrator, memory_extract, judge_eval |
| Chart | Planner chọn `chart_type`; FE Chart.js từ JSON spec |
| Multi-agent | Orchestrator 1–2 bước specialist → responder; không swarm |
