from __future__ import annotations

import argparse
import json
import sys
import time

from agent.config.logging import setup_logging


def cmd_llm_ping() -> int:
    from agent.config.settings import get_settings
    from agent.llm.provider import get_llm

    s = get_settings()
    llm = get_llm()
    t0 = time.perf_counter()
    resp = llm.invoke("Trả lời đúng một câu tiếng Việt: 1+1 bằng bao nhiêu?")
    dt = time.perf_counter() - t0
    print(f"model={s.llm_model}")
    print(f"base_url={s.llm_base_url}")
    print(f"latency_s={dt:.2f}")
    print(str(resp.content).strip())
    return 0


def cmd_db_ping() -> int:
    from agent.services.connection import ping

    row = ping()
    print(json.dumps(row, ensure_ascii=False, default=str))
    return 0


def cmd_ask(question: str) -> int:
    from agent.graph.graph import ask

    result = ask(question)
    out = {
        "question": result.get("question"),
        "intent": result.get("intent"),
        "intent_reason": result.get("intent_reason"),
        "sql": result.get("sql"),
        "sql_validation": result.get("sql_validation"),
        "error": result.get("error"),
        "answer": result.get("answer"),
        "row_count": (result.get("query_result") or {}).get("row_count"),
        "database": (result.get("query_result") or {}).get("database"),
        "doc_card_id": result.get("doc_card_id"),
        "doc_card_title": result.get("doc_card_title"),
        "chart_meta": result.get("chart_meta"),
        "has_chart": bool((result.get("chart_png_base64") or "").strip()),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    p = argparse.ArgumentParser(prog="agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("llm-ping", help="Test Qwen 8B qua Ollama")
    sub.add_parser("db-ping", help="SELECT 1 tới 192.168.1.200:18644")
    ask_p = sub.add_parser("ask", help="Hỏi đáp PostgreSQL")
    ask_p.add_argument("question")
    args = p.parse_args(argv)

    if args.cmd == "llm-ping":
        return cmd_llm_ping()
    if args.cmd == "db-ping":
        return cmd_db_ping()
    if args.cmd == "ask":
        return cmd_ask(args.question)
    p.error("unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
