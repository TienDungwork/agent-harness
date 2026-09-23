# v7 Chart UI audit — chỗ hiện chart trong chat

**Task:** Phase 2 — Rà soát chỗ hiện chart (slot / canvas / img PNG).  
**Ngày:** 2026-09-22 · **Chỉ audit** — polish bar/pie ở task tiếp theo.

---

## Luồng hiển thị

```text
SSE __chart__ / __answer__ detail
        → state.lastChart* (app.js)
        → appendMessage(..., chartPayload)
        → .chart-slot trong bubble assistant
              ├─ Chart.js → <canvas>     (ưu tiên nếu có spec + rows)
              ├─ <img> PNG base64        (fallback)
              └─ .chart-placeholder      (không có data)
```

---

## Chỗ hiện trong DOM / file

| Thành phần | File | Chi tiết |
|------------|------|----------|
| CDN Chart.js v4 | `frontend/index.html` | Script trước `app.js` |
| Slot container | `frontend/app.js` `appendMessage` | Mọi tin **assistant** luôn tạo `.chart-slot` |
| Canvas (bar/pie) | `renderChartJs()` | Tạo `<canvas>` trong slot; WeakMap `_chartInstances` |
| PNG fallback | `appendMessage` | `<img src="data:image/png;base64,...">` |
| Placeholder | `appendMessage` | `.chart-placeholder` + icon + text “Khu vực biểu đồ…” |
| CSS slot | `frontend/style.css` | `.chart-slot`, `.chart-slot canvas` (min-height 200px), `.chart-placeholder` |
| Reload session | `loadCurrentSessionMessages` | Gọi `appendMessage` với `msg.chart` đã lưu |

---

## Payload hợp lệ

`chartPayload` object:

```js
{ png: string|null, spec: { x_column, y_column, title_vi, chart_type? }, type: 'bar'|'pie', rows: [...] }
```

Hoặc legacy: string = PNG base64 thuần.

**Điều kiện Chart.js:** `spec.x_column` + `spec.y_column` + `rows.length > 0` + `typeof Chart !== 'undefined'`.

**SSE:** `node_id === '__chart__'` set `lastChart`, `lastChartSpec`, `lastChartType`, `lastChartRows`; khi `__answer__` gộp vào `chartPayload`.

---

## Gap cho polish (task sau — chưa làm)

| Gap | Ghi chú |
|-----|---------|
| Bar | **DONE (Phase 2 bar polish)**: đã bổ sung `CHART_VI_LABELS`, `formatChartLabel`, fallback title tiếng Việt, palette tương phản cao, beginAtZero trên trục Y, và `.chart-canvas-wrapper` chống méo/blank |
| Pie | **DONE (Phase 2 pie polish)**: legend position bottom với nhãn tiếng Việt (`formatChartLabel`), tỷ lệ % rõ ràng trên legend (`label: %`) và tooltip (`colLabel: val (%)`), viền phân cách lát cắt trắng tương phản |
| Placeholder | **DONE (Phase 2 placeholder / empty state)**: chỉ tạo và gắn `.chart-slot` khi có `chartPayload`; tin nhắn thông thường không còn hiện placeholder làm che text |
| PNG | Inline style; chưa theme thống nhất với Chart.js |
| Empty chart | **DONE (Phase 2 placeholder / empty state)**: khi có payload chart nhưng rows rỗng hoặc thiếu spec/png, hiển thị empty state gọn gàng (`.chart-slot-empty`, "Chưa có dữ liệu để hiển thị biểu đồ") không choán giao diện |

> **Cập nhật:** Gap **Bar**, **Pie**, **Placeholder**, và **Empty chart** đã hoàn thành và được kiểm tra bằng pytest. Cập nhật checklist smoke UI ở task kế tiếp.

---

## Kết luận audit

- Wiring đủ: **slot + canvas Chart.js + img PNG + placeholder**.
- Ưu tiên render: Chart.js → PNG → placeholder.
- Phase 2 tiếp: polish bar → polish pie → placeholder chỉ khi phù hợp → cập nhật smoke checklist.

---

## Review vs product-spec / test-plan (task audit này)

| Nguồn | Tiêu chí | Kết quả |
|-------|----------|---------|
| implementation-plan Phase 2 #1 | Rà soát slot / canvas / img PNG | **Pass** — doc + pytest wiring |
| test-plan **SSE chart** | FE wiring test (app.js) | **Pass** — `tests/test_phase2_chart_ui_audit.py` + `test_frontend_chartjs.py` |
| product-spec AC #7 | Chart bar/pie đẹp, nhãn VI, màu rõ | **Missing (đúng scope)** — chưa thuộc task audit; ghi gap ở trên |
| test-plan **Chart** detect/fallback/title | Backend chart quality | **Missing (đúng scope)** — Phase 3d / polish bar-pie |

**Fail liên quan task này:** không có.  
**Không sửa FE chart trong review này** — tránh làm sớm task polish.
