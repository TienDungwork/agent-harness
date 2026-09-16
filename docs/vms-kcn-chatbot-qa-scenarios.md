# Kịch bản QA — Chatbot VMS (Agent Canvas)

**Mục đích:** Kiểm tra chatbot hỗ trợ **vận hành / điều hành khu công nghiệp** — số liệu biển số, ra/vào, hãng xe, truy vết, xâm nhập — qua hội thoại tiếng Việt trên Agent Canvas (Home → chat mới).

**Phạm vi dữ liệu:** ClickHouse VMS (`vms.ai_events`), org scope theo cấu hình gateway. Agent **không** được bịa số; phải gọi MCP **`vms_query`** (lean path).

**Lưu ý kho (hay gặp “không có dữ liệu”):** sync có thể trễ hơn ngày lịch “hôm nay”. `plate_flow` / `manufacturer` / `intrusion` (và `count` không truyền `day`) **tự fallback** sang ngày gần nhất còn dữ liệu và ghi rõ trong `reply_vi` (*Hôm nay chưa có dữ liệu; dùng ngày gần nhất…*). Không coi đó là FAIL nếu số liệu khớp ngày fallback.

---

## Điều kiện tiên quyết

| Hạng mục | Yêu cầu |
|----------|---------|
| Stack | `agent-canvas` + `local-gateway` + `infra-mcp` + ClickHouse đã sync |
| MCP | Conversation create có `creanova_infra`; tool `vms_query` khả dụng |
| LLM | Model hỗ trợ function call (Ollama/Qwen local hoặc tương đương) |
| Ngôn ngữ | Câu trả lời **tiếng Việt**, ngắn; có `reply_vi` thì **copy đúng nội dung** (không paraphrase tiếng Anh) |
| Thời gian | “Hôm nay” = ngày lịch **Asia/Ho_Chi_Minh (UTC+7)** theo CLOCK hệ thống |

**Tiêu chí chung PASS**

- Agent gọi đúng `vms_query` với `action` phù hợp (không viết SQL, không đoán).
- Nội dung trả lời khớp `reply_vi` từ tool (số liệu nhất quán).
- Không lỗi vòng lặp *“Your last response did not include a function call or a message”*.
- Nếu payload tool có `chart`, UI hiển thị **biểu đồ** dưới tin nhắn (component `VmsAnalyticsChart`).

**Tiêu chí chung FAIL**

- Trả lời số không qua tool / số khác `reply_vi`.
- Trả lời tiếng Anh hoặc `<tool_call>` raw trong chat.
- Yêu cầu phân loại **số chỗ** (5/7/9/16/29/40) mà agent **bịa** breakdown — kho **chưa có** trường số chỗ (`seats_available: false`).

---

## Bảng kịch bản

| ID | Nghiệp vụ | `vms_query` |
|----|-----------|-------------|
| KCN-01 | Ra/vào hôm nay — xe máy & ô tô (+ biểu đồ) | `action=flow`, bỏ `day` hoặc ngày hôm nay |
| KCN-02 | Ra/vào + phân loại chi tiết (giới hạn số chỗ) | `action=flow` + giải thích giới hạn dữ liệu |
| KCN-03 | Ô tô theo hãng hôm nay | `action=manufacturer`, `vehicle_type=CAR` |
| KCN-04 | Truy vết biển số | `action=trace`, `q=<biển>` |
| KCN-05 | Khung giờ xâm nhập nhiều nhất hôm nay | `action=intrusion` |

---

## KCN-01 — Biểu đồ lượt ra/vào (xe máy, ô tô)

**Mục tiêu:** Ban điều hành xem nhanh **lượt ra vào hôm nay**, tách **xe máy** và **ô tô**, có trực quan biểu đồ.

**Câu hỏi mẫu (copy-paste):**

```text
Biểu đồ hôm nay có bao nhiêu lượt xe ra và vào, phân loại theo xe máy, ô tô?
```

**Kỳ vọng kỹ thuật**

- Gọi: `vms_query(action="flow")` (không truyền `day` nếu ý là hôm nay).
- `reply_vi` gồm: tổng lượt, tách **Vào / Ra** (IN/OUT), breakdown **xe máy / ô tô / tải** (theo `vehicle_type` trong kho).
- Có thể kèm dòng *“Lưu ý: kho hiện chưa có số chỗ (5/7/9/16…) — chỉ có loại xe máy/ô tô/tải.”*

**PASS**

- [ ] Tool `flow` được gọi.
- [ ] Trả lời tiếng Việt, số khớp tool.
- [ ] Có **biểu đồ** (bar) khi observation chứa `chart`.

**FAIL**

- [ ] Chỉ gọi `count` tổng mà không breakdown ra/vào × loại khi user hỏi rõ “ra và vào” + “phân loại”.
- [ ] Không có biểu đồ dù tool trả `chart`.

---

## KCN-01b — Biểu đồ số lượng xe trong tháng (line)

**Câu hỏi mẫu:**

```text
vẽ biểu đồ số lượng xe trong tháng 9 đến nay
```

**Kỳ vọng:** `vms_query(action="count", month="2026-09")` — **không** `day=hôm nay`, **không** `vehicle_type` trừ khi user nói rõ loại. `reply_vi` dạng *Từ 01/09/… đến …: tổng N (K ngày)*. Chart type **line** (`per_day`).

**FAIL:** trả lời một ngày / chỉ xe máy / `day` + `vehicle_type` thay vì `month`.

---

## KCN-02 — Thống kê ra/vào + phân loại theo số chỗ (giới hạn nghiệp vụ)

**Mục tiêu:** Kiểm tra chatbot **phục vụ điều hành** khi user yêu cầu phân loại **theo số chỗ** (5/7/9/16/29/40) — hiện **chưa có trong warehouse**.

**Câu hỏi mẫu (copy-paste):**

```text
Biểu đồ thống kê hôm nay có bao nhiêu lượt ra và vào. Phân loại theo xe máy, xe tải, xe 5 chỗ, xe 7 chỗ, xe 9 chỗ, xe 16 chỗ, xe 29 chỗ, xe 40 chỗ.
```

**Kỳ vọng kỹ thuật**

- Gọi: `vms_query(action="flow")` cho phần **ra/vào** và loại xe có trong kho: **MOTORCYCLE**, **TRUCK**, **CAR** (và UNKNOWN nếu có).
- Agent **không** invent cột 5 chỗ / 7 chỗ / …
- Trả lời phải **nêu rõ giới hạn** (đúng tin trong `reply_vi` hoặc tương đương): chưa có số chỗ; chỉ phân loại xe máy / ô tô / tải.

**PASS**

- [ ] `flow` được gọi.
- [ ] Có số liệu ra/vào + xe máy / ô tô / tải (nếu có dữ liệu).
- [ ] **Không** liệt kê số giả cho 5/7/9/16/29/40 chỗ.
- [ ] Giải thích ngắn gọn vì sao chưa tách theo số chỗ.
- [ ] Biểu đồ hiển thị nếu tool trả `chart` (thường theo hướng IN/OUT × loại xe).

**FAIL**

- [ ] Bịa breakdown 5/7/9 chỗ.
- [ ] Từ chối hoàn toàn mà không đưa số `flow` thay thế.

**Ghi chú triển khai tương lai:** Khi attrs số chỗ có trên ClickHouse, bổ sung kịch bản KCN-02b và đổi tiêu chí PASS.

---

## KCN-03 — Số liệu ô tô theo hãng (hôm nay)

**Mục tiêu:** Hỗ trợ điều hành theo dõi **cơ cấu hãng xe** (ô tô) trong ngày.

**Câu hỏi mẫu (copy-paste):**

```text
Số liệu ô tô theo hãng xe trong hôm nay.
```

**Kỳ vọng kỹ thuật**

- Gọi: `vms_query(action="manufacturer", vehicle_type="CAR")` (bỏ `day` = hôm nay).
- `reply_vi`: top hãng + số lượng, tổng ô tô trong ngày (theo API `plate_by_manufacturer`).

**PASS**

- [ ] `manufacturer` + `vehicle_type=CAR`.
- [ ] Tiếng Việt, số khớp tool.
- [ ] Biểu đồ (nếu có `chart` trong payload).

**FAIL**

- [ ] Gọi `flow` hoặc `count` thay vì `manufacturer` khi user hỏi rõ “theo hãng”.
- [ ] Dùng `MOTORBIKE` thay vì `MOTORCYCLE` (invalid).

---

## KCN-04 — Truy vết / lịch sử biển số

**Mục tiêu:** Tra cứu **lịch sử di chuyển** một phương tiện theo biển — phục vụ an ninh / vận hành cổng.

**Câu hỏi mẫu (copy-paste):**

Thay `{BIỂN_SỐ}` bằng biển thật có trong hệ thống (ví dụ `14H03464`, `30A-12345`):

```text
Truy vết, lịch sử di chuyển của phương tiện có biển số {BIỂN_SỐ}.
```

**Kỳ vọng kỹ thuật**

- Gọi: `vms_query(action="trace", q="{BIỂN_SỐ}")`.
- Mặc định: cửa sổ ~90 ngày, top mốc gần nhất (limit 5 trừ khi user yêu cầu khác).
- `reply_vi`: danh sách mốc thời gian / camera / hướng (theo dữ liệu search-plate), hoặc thông báo không tìm thấy.

**PASS**

- [ ] `trace` với đúng `q` (không nhầm ngày vào `q`).
- [ ] Không dùng `count` cho câu truy vết.
- [ ] Trả lời tiếng Việt, khớp `reply_vi`.

**FAIL**

- [ ] Agent hỏi lại biển khi user đã cung cấp `{BIỂN_SỐ}` hợp lệ.
- [ ] Trả lời bịa lịch sử không có trong tool.

---

## KCN-05 — Khung giờ xâm nhập nhiều nhất (hôm nay)

**Mục tiêu:** Điều phối an ninh — biết **giờ cao điểm xâm nhập** trong ngày (module ANOMALY / INTRUSION_DETECTION).

**Câu hỏi mẫu (copy-paste):**

```text
Khung thời gian xảy ra xâm nhập nhiều nhất ngày hôm nay.
```

**Kỳ vọng kỹ thuật**

- Gọi: `vms_query(action="intrusion")` (không `day` = hôm nay).
- `reply_vi`: giờ peak (0–23), số sự kiện; hoặc “không có sự kiện xâm nhập” nếu `total_n = 0`.

**PASS**

- [ ] `intrusion` được gọi.
- [ ] Nêu rõ khung giờ (VN) và số liệu / không có dữ liệu.
- [ ] Biểu đồ giờ (nếu có `chart`).

**FAIL**

- [ ] Nhầm sang `flow` (biển số) hoặc `trace`.
- [ ] Bịa giờ peak khi tool báo 0 sự kiện.

---

## Thứ tự chạy gợi ý

1. **KCN-01** (flow cơ bản + chart)
2. **KCN-03** (manufacturer)
3. **KCN-05** (intrusion)
4. **KCN-04** (trace — cần biển có dữ liệu)
5. **KCN-02** (kiểm tra từ chối/bịa số chỗ)

Mỗi case: **conversation mới** hoặc tin nhắn follow-up sau lời chào; tránh reuse conversation cũ sai model/MCP.

---

## Tham chiếu kỹ thuật

- Prompt agent: `agent-canvas/config/SOUL.md`, skill `vms-analytics`
- Tool: `services/infra-mcp/mcp_stdio.py` → `vms_query`
- API: `services/local-gateway/infra/analytics.py` (`plate_flow`, `plate_by_manufacturer`, `intrusion_peak`, search-plate)
- E2E một câu đếm xe: `.pr/e2e_vms_self_chat.py` (không thay full manual QA trên UI)
- Ma trận test Agent Canvas: `agent-canvas/docs/TESTING_MATRIX.md`

---

## Biên bản test (mẫu)

| ID | Người test | Ngày | PASS/FAIL | Ghi chú |
|----|------------|------|-----------|---------|
| KCN-01 | agent | 16/09/2026 | PASS | `flow` + day=today → fallback **08/09**: 1872 (Vào 74 / Ra 1798; xe máy 1097, ô tô 706) |
| KCN-02 | agent | 16/09/2026 | PASS | `flow`; nêu chưa có số chỗ; không bịa 5/7/9… |
| KCN-03 | agent | 16/09/2026 | PASS | `manufacturer` CAR → fallback **08/09**: tổng 704 (VINFAST 127, KIA 90, …) |
| KCN-04 | agent | 16/09/2026 | PASS | `trace` q=14H03464 → 3 mốc (25/08, 17/08×2) |
| KCN-05 | agent | 16/09/2026 | PASS | `intrusion` → fallback **27/08**: peak **09:00–09:59** (151/951) |







Biểu đồ ngày 08/09/2026 có bao nhiêu lượt xe ra và vào, phân loại theo xe máy, ô tô?
Số liệu ô tô theo hãng xe ngày 08/09/2026.
Truy vết, lịch sử di chuyển của phương tiện có biển số 15HC00507.
Khung thời gian xảy ra xâm nhập nhiều nhất ngày 27/08/2026.
