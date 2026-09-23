# Product Spec — agent dong v7

**Trạng thái:** Spec only — chưa implement.  
**Baseline:** v6 đang chạy (Docker + UI session + QueryPlan).  
**v7:** Học `agent-harness/duy` — text-to-SQL nhanh hơn, chào hỏi trả lời ngay, biểu đồ dễ đọc hơn, rồi dọn code chết.

---

## App goal

Trợ lý tiếng Việt cho vận hành VMS KCN Hưng Phú: hỏi số liệu (read-only), hỏi hướng dẫn VMS/AIOC, xem biểu đồ rõ — nhanh hơn v6, chạy production bằng Docker.

---

## Target users

| Ai | Họ làm gì với app |
|----|-------------------|
| Vận hành KCN | Hỏi tiếng Việt; đổi session; xem số liệu / hướng dẫn / biểu đồ — không viết SQL |
| Dev / reviewer | Chạy Docker, pytest, smoke, eval golden-30 |

---

## Core user flow

1. Mở UI → chọn hoặc tạo **session** (cột trái).
2. Gõ câu hỏi tiếng Việt.
3. Hệ thống kiểm tra an toàn (guardrail) → phân loại câu hỏi.
4. Chọn một đường xử lý:
   - **Chào hỏi / ngoài phạm vi** → trả lời ngay (không truy vấn DB).
   - **Hướng dẫn** → lấy tài liệu VMS/AIOC → trả lời.
   - **Số liệu** → chuẩn bị schema gọn → sinh SQL → kiểm tra/sửa → chạy DB → (nếu cần) biểu đồ đẹp → trả lời ngắn.
5. UI hiện câu trả lời + biểu đồ; session nhớ ngữ cảnh ngắn; câu trùng trong 5 phút lấy cache.
6. (Tuỳ chọn) Live graph hiện từng bước xử lý để debug.

```text
câu hỏi → phân loại
              ├─ chào / ngoài phạm vi → trả lời ngay → xong
              ├─ hướng dẫn → docs → xong
              └─ số liệu → chuẩn bị → sinh SQL → kiểm tra → chạy DB
                            → trả lời (+ biểu đồ nếu cần) → xong
```

---

## Features in scope

**Giữ từ v6 (vẫn dùng):**

- Docker là đường chạy chính; UI session + stream trả lời.
- Memory theo session / user; cache câu trùng 5 phút.
- Guardrails; prompts trong `resource/`; docs VMS/AIOC.
- Đổi LLM: self-hosted @ 196 hoặc OpenAI.
- Trace / live graph (debug).

**Làm mới trong v7:**

- Chào hỏi (`chào bạn`, …) → trả lời thẳng từ LLM, không chạy SQL.
- Nhánh số liệu = **text-to-SQL** + kiểm tra SQL bắt buộc (chỉ SELECT, bảng/cột trong whitelist).
- **Trước SQL:** chọn ít bảng liên quan, gắn khung thời gian, gợi ý GROUP BY cho biểu đồ.
- **Sau SQL:** câu đếm đơn giản trả lời nhanh (không gọi LLM thừa); biểu đồ **bar/pie dễ đọc** (nhãn tiếng Việt, title, màu rõ) — học pattern duy.
- Dọn code / prompt không dùng production; cập nhật README, AGENTS, sơ đồ.

---

## Features out of scope

- Web search, MCP, swarm agent phức tạp.
- Ghi DB production; path ClickHouse mới.
- Graph editor / dashboard analytics ngoài chat.
- Backend Ollama; sync prompt lên Langfuse Cloud.
- Giữ ReAct tool-calling cũ làm đường product.
- Redesign UI toàn bộ (chỉ chỉnh chỗ chart/session nếu cần).

---

## Acceptance criteria

1. `pytest -q` xanh sau mỗi task và khi kết thúc v7.
2. `"xin chào"` / `"chào bạn"` → một lần gọi LLM; không chạy SQL / docs.
3. Câu đếm đơn giản (1 dòng số) → trả lời nhanh khi khớp rule; không gọi LLM respond thừa.
4. Nhánh số liệu: sinh SQL → kiểm tra → chạy; sửa tối đa 2 lần; chặn DDL/DML.
5. Không gửi full catalog mỗi lần — chỉ schema đã chọn.
6. Khung thời gian (hôm nay / hôm qua / …) có khi sinh SQL.
7. Câu yêu cầu biểu đồ → bar hoặc pie hiện trên UI: có title, nhãn tiếng Việt, màu rõ; không trống / không khó đọc.
8. Cùng câu trong 5 phút → cache hit.
9. `./scripts/smoke-production.sh` pass trên Docker + gateway 196.
10. Eval golden-30 ≥ 28/30; cập nhật `eval/results/golden-30.md`.
11. Đã gỡ code chết không product; README + AGENTS + sơ đồ khớp flow v7.

---

## Ghi chú (không mở rộng scope)

- SQL: text-to-SQL + validator (học duy); không dùng QueryPlan làm path chính.
- Chart: học duy (gợi ý → fallback → render đẹp).
- Tốc độ: ít lần gọi LLM; bỏ bước thừa với câu đơn giản.
- Tham chiếu code: `agent-harness/duy`.
