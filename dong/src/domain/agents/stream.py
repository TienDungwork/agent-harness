"""SSE stream queue helpers for graph nodes."""

from __future__ import annotations

import contextvars

_stream_queue = contextvars.ContextVar("_stream_queue", default=None)


def emit_answer_chunks(ans_text: str, chunk_words: int = 3, enabled: bool = True) -> None:
    """Phát các SSE chunk event cho câu trả lời thời gian thực qua _stream_queue."""
    if not enabled:
        return
    q = _stream_queue.get()
    if q is None or not ans_text:
        return
    words = ans_text.split(" ")
    for i in range(0, len(words), chunk_words):
        group = words[i : i + chunk_words]
        delta = " ".join(group)
        if i + chunk_words < len(words):
            delta += " "
        q.put({"node_id": "__answer__", "status": "chunk", "delta": delta})
