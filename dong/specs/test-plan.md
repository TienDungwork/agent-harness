# Test Plan — dong v4

Người dùng tự chạy sau từng phase. Chưa code mới cho đến khi phase xong.

## Offline

```bash
cd agent-harness/dong
pytest -q
find tests -name 'test_*.py' | wc -l   # < 10
test ! -d backend
```

| Chủ đề | Kỳ vọng |
|--------|---------|
| Guardrail | injection 400; thời tiết = ngoài phạm vi |
| Intent | số liệu / how-to / từ chối đúng nhánh |
| Read-only | `DELETE` không tới DB |
| Docs | how-to không gọi `count_vehicle_flow` |
| LLM | mock client, không gọi 196 |
| Trace/cache | monitoring tắt = no-op; cache hit |
| API | `/api/health`, chat/ask |
| Stream node | mock SSE: thứ tự node + có input/output khi done |
| Eval report | đủ 30 dòng (có thể mock answer) |
| UI graph (smoke) | panel nửa rộng tồn tại; handler hover gắn node done |

## Live

```bash
python -c "from src.llm import ping; print(ping())"
# mở frontend, gửi một câu số liệu và một câu how-to
```

| Case | Kỳ vọng |
|------|---------|
| Ping 196 | HTTP 200 |
| Graph realtime | node hiện lần lượt trong khung ≈ nửa màn hình |
| Hover/click | thấy input và output node đã chạy |
| Câu mới | graph reset rồi vẽ lại |

## Golden 30 (Phase 8)

Cần `.env` LLM 196 + DB read-only. **Không** set `PYTEST_CURRENT_TEST`.

```bash
python eval/run.py
python eval/run.py --judge
```

Đọc `eval/results/golden-30.md`: header `mode: live`, cột `id`, `slice`, `pass/fail`, `latency_ms`, `tool`, `note`, `judge`.
