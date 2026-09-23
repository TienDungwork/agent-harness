# Test Plan — agent dong v7

**Trạng thái:** Spec only. Verify **sau từng task** trong `implementation-plan.md`.  
**Baseline:** pytest v6 xanh; Docker + smoke script đã có.

---

## Offline (pytest)

```bash
cd agent-harness/dong
pytest -q
```

| Chủ đề | Kỳ vọng |
|--------|---------|
| **Classify fast path** | Chào hỏi → END sớm, không node SQL (`tests/test_classify_fast_path.py`) |
| **Pre-SQL** | Schema ≤4 bảng; time_range + chart hint trong prompt — acceptance pytest: `tests/test_phase3b_pre_sql_context.py` (16 tests, Phase 3b done) |
| **generate_sql** | Extract SQL fenced; empty → lỗi rõ |
| **validate / repair** | SELECT-only; DDL fail; repair ≤2 |
| **execute** | Re-validate trước chạy (mock PG) |
| **Simple answer** | 1-row COUNT → template; không gọi respond LLM |
| **Chart** | Detect bar/pie; fallback mock; PNG/spec không rỗng; nhãn/meta có title |
| **SSE chart** | Event chart tới FE; FE wiring test (`tests/test_phase2_chart_ui_audit.py`, `test_frontend_chartjs.py`); audit: `specs/v7-chart-ui-audit.md` |
| **Errors** | Stream không crash; message ngắn VI |
| **Regression** | Sessions, TTL, guardrails, Docker spec vẫn pass |
| **Cleanup** | Sau Phase 8: graph không import dead modules |

### File test dự kiến (tạo khi implement)

- `tests/test_classify_fast_path.py`
- `tests/test_pre_sql_retrieval.py`
- `tests/test_sql_generation.py`
- `tests/test_post_sql_chart.py`
- Giữ: `test_memory_*`, `test_phase5_*`, `test_phase7_*`

---

## Live — Docker + LLM 196

```bash
docker compose up --build -d
./scripts/verify-docker-self-hosted.sh
./scripts/smoke-production.sh
```

| Case | Kỳ vọng |
|------|---------|
| Greeting | `"chào bạn"` nhanh, không SQL trên live graph |
| Stat simple | COUNT → trả lời ngắn / template |
| Chart bar | UI hiện cột rõ, nhãn category VI, title VI, canvas không méo/blank, tooltip số liệu |
| Chart pie | UI hiện tròn rõ, legend đọc được với nhãn VI + %, tooltip có %, lát cắt rõ |
| Fire / AIOC | Smoke cases pass |
| TTL | Lần 2 = cache hit |

Checklist UI chi tiết: `specs/smoke-manual-checklist.md` (đã cập nhật Phase 2; kiểm thử smoke live toàn diện ở Phase 7).

---

## Eval golden-30

```bash
python eval/run.py
python eval/run.py --judge
```

| Metric | Target |
|--------|--------|
| Pass | ≥28/30 |
| Output | `eval/results/golden-30.md` |
| Log | Delta vs baseline trong `specs/change-log.md` |

---

## Review mỗi task

1. Diff đúng scope task.
2. `pytest -q` xanh.
3. Manual / smoke nếu chạm API hoặc UI chart.
4. Cập nhật `specs/change-log.md`.

## Không bắt buộc mỗi commit

- Full golden live (chỉ Phase 9).
- Browser E2E tự động.
