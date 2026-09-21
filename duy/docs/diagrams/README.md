# Sơ đồ LangGraph agent DUY

Xuất bằng API chính thức của LangGraph:

```bash
uv run python - <<'PY'
from pathlib import Path
from agent.graph.graph import build_graph, reset_app

reset_app()
g = build_graph().get_graph()
Path("docs/diagrams/agent-graph.mmd").write_text(g.draw_mermaid(), encoding="utf-8")
Path("docs/diagrams/agent-graph.png").write_bytes(g.draw_mermaid_png())
print("ok")
PY
```

- Mermaid: [`agent-graph.mmd`](./agent-graph.mmd)
- PNG: [`agent-graph.png`](./agent-graph.png)

Luồng chính sau `classify_intent`:

| Intent | Nhánh |
|--------|--------|
| `query_db` | schema → SQL → validate → execute → chart → respond (+ repair) |
| `how_to` / `troubleshoot` / `concept` | retrieve_docs → answer_from_docs |
| `web_search` | web_search → answer_from_web |
| `chat` / `clarify` / `out_of_scope` | respond_without_sql hoặc END nếu đã có answer |
