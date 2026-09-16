---
name: vms-analytics
description: ClickHouse VMS analytics via one MCP tool vms_query.
---

# VMS analytics

Use **`vms_query`** only (lean MCP — no SSH tools).

| Intent | `action=` | Args |
|---|---|---|
| Đếm xe / biển / một ngày | `count` | `day=YYYY-MM-DD` or omit (latest) |
| Nhiều ngày rời | `count` | `days_list=YYYY-MM-DD,…` |
| Tháng đến nay / biểu đồ tháng | `count` | `month=YYYY-MM` (line chart) — **không** `vehicle_type` trừ khi hỏi rõ loại |
| Ra/vào + loại xe | `flow` | `day?` |
| Ô tô theo hãng | `manufacturer` | `day?`, `vehicle_type=CAR` |
| Truy vết biển | `trace` | `q=<biển>` |
| Xâm nhập peak | `intrusion` | `day?` |

Copy **`reply_vi`** then Finish. Never invent numbers. Seats (5/7/9…) not in warehouse yet.
