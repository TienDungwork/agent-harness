"""Monitoring hooks — Phase 5 (Langfuse Observability & Token Metrics).

Tối thiểu: 1 trace cho mỗi lượt gọi `/api/chat` hoặc `/ask`, gắn question/answer/output/token/latency/lỗi.
Nested child spans: `chon_tool` / `chay_tool` / `dien_giai` qua `trace_step`.
KHÔNG bọc qua LangChain callback handlers — dùng Langfuse SDK trực tiếp để kiểm soát chính xác payload.

Cơ chế Fail-safe & No-op:
- Mặc định tắt (`MONITORING_ENABLED=false`): Toàn bộ hàm no-op, không tạo kết nối mạng.
- Khi bật (`MONITORING_ENABLED=true`): Nếu Langfuse server tạm thời down, timeout hoặc lỗi kết nối,
  hệ thống tự động bắt lỗi an toàn (fail-safe) và tiếp tục trả lời bình thường, KHÔNG làm crash API.
"""

from __future__ import annotations

import contextvars
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

_request_tokens = contextvars.ContextVar("request_tokens", default=None)

def add_request_tokens(usage: dict[str, int]):
    """Cộng dồn token vào request hiện tại."""
    tokens = _request_tokens.get()
    if tokens is not None and isinstance(usage, dict):
        tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
        tokens["completion_tokens"] += usage.get("completion_tokens", 0)
        tokens["total_tokens"] += usage.get("total_tokens", 0)


def _get_langfuse():
    """Lazy import + lazy client — tránh phụ thuộc cứng vào package
    `langfuse` khi `MONITORING_ENABLED=false`, và tránh tạo client ở
    import-time."""
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def extract_token_usage(response: Any) -> dict[str, int]:
    """Trích xuất prompt_tokens, completion_tokens, total_tokens từ response của LLM.

    Hỗ trợ:
    - LangChain AIMessage (usage_metadata hoặc response_metadata['token_usage'])
    - Dictionary response (keys: usage, usage_metadata, token_usage)
    - Đối tượng phản hồi chuẩn OpenAI ChatCompletions
    """
    if not response:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # 1. Kiểm tra usage_metadata (LangChain AIMessage chuẩn)
    usage_meta = getattr(response, "usage_metadata", None)
    if isinstance(usage_meta, dict):
        p = usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens") or 0
        c = usage_meta.get("output_tokens") or usage_meta.get("completion_tokens") or 0
        tot = usage_meta.get("total_tokens") or (p + c)
        return {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(tot)}

    # 2. Kiểm tra response_metadata['token_usage']
    resp_meta = getattr(response, "response_metadata", None)
    if isinstance(resp_meta, dict):
        tu = resp_meta.get("token_usage")
        if isinstance(tu, dict):
            p = tu.get("prompt_tokens") or tu.get("input_tokens") or 0
            c = tu.get("completion_tokens") or tu.get("output_tokens") or 0
            tot = tu.get("total_tokens") or (p + c)
            return {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(tot)}

    # 3. Fallback nếu response là dict
    if isinstance(response, dict):
        usage = response.get("usage") or response.get("usage_metadata") or response.get("token_usage")
        if isinstance(usage, dict):
            p = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            c = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            tot = usage.get("total_tokens") or (p + c)
            return {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(tot)}

    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@contextmanager
def trace_answer(name: str, question: str, metadata: dict[str, Any] | None = None):
    """Bọc quanh 1 lượt gọi pipeline `/ask` hoặc `/api/chat`.

    Dùng như:
        with trace_answer("chat", question, metadata={"endpoint": "/api/chat"}) as t:
            result = ...
            t["output"] = result

    `t["_span"]` là span cha đang mở — truyền xuống cho `trace_step()` để
    tạo nested span. Ghi nhận đầy đủ output, token metrics (prompt_tokens,
    completion_tokens, total_tokens), model_name, temperature, latency_s.

    Fail-safe: Nếu Langfuse server tạm thời down hoặc lỗi kết nối,
    hệ thống bắt lỗi an toàn và tiếp tục pipeline bình thường, không crash API.
    """
    if not settings.monitoring_enabled:
        yield {}
        return

    span = None
    langfuse = None
    start = time.perf_counter()
    box: dict[str, Any] = {}
    meta = dict(metadata or {})
    
    token_counter = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    token_var_token = _request_tokens.set(token_counter)

    try:
        langfuse = _get_langfuse()
        span = langfuse.start_observation(name=name, input=question, metadata=meta)
        box["_span"] = span
    except Exception as exc:
        logger.warning("Không thể khởi tạo Langfuse trace (fail-safe active): %s", exc)
        span = None

    try:
        yield box
    except Exception as exc:
        if span is not None:
            try:
                if "output" not in box or box.get("output") is None:
                    box["output"] = {"error": str(exc)}
                span.update(level="ERROR", status_message=str(exc))
            except Exception as update_exc:
                logger.warning("Lỗi cập nhật Langfuse ERROR span: %s", update_exc)
        raise
    finally:
        if "usage" not in box:
            box["usage"] = {}
        box["usage"]["prompt_tokens"] = box["usage"].get("prompt_tokens", 0) + token_counter["prompt_tokens"]
        box["usage"]["completion_tokens"] = box["usage"].get("completion_tokens", 0) + token_counter["completion_tokens"]
        box["usage"]["total_tokens"] = box["usage"].get("total_tokens", 0) + token_counter["total_tokens"]
        try:
            _request_tokens.reset(token_var_token)
        except ValueError:
            pass  # SSE chạy qua threadpool — context khác, vẫn phải end span

        if span is not None:
            try:
                latency_s = time.perf_counter() - start
                out = box.get("output")
                if out is None:
                    out = {"status": "completed"}

                model_name = box.get("model_name") or meta.get("model_name") or (
                    settings.model_name if settings.llm_backend == "self_hosted" else settings.llm_model
                )
                temperature = box.get("temperature", meta.get("temperature", settings.llm_temperature))

                usage = box.get("usage") or {}
                p_tokens = int(usage.get("prompt_tokens", meta.get("prompt_tokens", 0)))
                c_tokens = int(usage.get("completion_tokens", meta.get("completion_tokens", 0)))
                tot_tokens = int(usage.get("total_tokens", meta.get("total_tokens", p_tokens + c_tokens)))

                meta.update({
                    "latency_s": latency_s,
                    "model_name": model_name,
                    "temperature": temperature,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": tot_tokens,
                })

                update_kwargs: dict[str, Any] = {
                    "output": out,
                    "metadata": meta,
                    "model": model_name,
                    "model_parameters": {"temperature": temperature},
                }
                if tot_tokens > 0 or p_tokens > 0 or c_tokens > 0:
                    update_kwargs["usage_details"] = {
                        "input": p_tokens,
                        "output": c_tokens,
                        "total": tot_tokens,
                    }

                span.update(**update_kwargs)
                span.end()
            except Exception as update_exc:
                logger.warning("Lỗi kết thúc Langfuse span: %s", update_exc)

            try:
                if langfuse is not None:
                    langfuse.flush()
            except Exception as flush_exc:
                logger.warning("Lỗi flush Langfuse: %s", flush_exc)


@contextmanager
def trace_step(parent_span: Any, name: str, input: Any = None, metadata: dict[str, Any] | None = None):
    """Nested child span dưới `parent_span` (lấy từ `trace_answer`'s `t["_span"]`).

    Dùng trong pipeline agent để thấy từng bước (chon_tool/chay_tool/dien_giai)
    lồng nhau trong Langfuse. Lưu trữ đầy đủ output, token metrics, model, latency_s.
    No-op nếu `parent_span` là `None` (monitoring tắt hoặc chạy ngoài trace).

    Fail-safe: Bắt mọi lỗi cập nhật/kết thúc span để không làm gián đoạn Agent.
    """
    if parent_span is None:
        yield {}
        return

    start = time.perf_counter()
    span = None
    box: dict[str, Any] = {}
    meta = dict(metadata or {})

    try:
        span = parent_span.start_observation(name=name, input=input, metadata=meta)
        box["_span"] = span
    except Exception as exc:
        logger.warning("Không thể tạo Langfuse child span '%s' (fail-safe active): %s", name, exc)
        span = None

    try:
        yield box
    except Exception as exc:
        if span is not None:
            try:
                if "output" not in box or box.get("output") is None:
                    box["output"] = {"error": str(exc)}
                span.update(level="ERROR", status_message=str(exc))
            except Exception as update_exc:
                logger.warning("Lỗi cập nhật child span ERROR: %s", update_exc)
        raise
    finally:
        if span is not None:
            try:
                latency_s = time.perf_counter() - start
                out = box.get("output")
                if out is None:
                    out = {"status": "completed"}

                model_name = box.get("model_name") or meta.get("model_name")
                temperature = box.get("temperature", meta.get("temperature"))

                meta["latency_s"] = latency_s
                if model_name:
                    meta["model_name"] = model_name
                if temperature is not None:
                    meta["temperature"] = temperature

                usage = box.get("usage") or {}
                p_tokens = int(usage.get("prompt_tokens", meta.get("prompt_tokens", 0)))
                c_tokens = int(usage.get("completion_tokens", meta.get("completion_tokens", 0)))
                tot_tokens = int(usage.get("total_tokens", meta.get("total_tokens", p_tokens + c_tokens)))

                if tot_tokens > 0 or p_tokens > 0 or c_tokens > 0:
                    meta["prompt_tokens"] = p_tokens
                    meta["completion_tokens"] = c_tokens
                    meta["total_tokens"] = tot_tokens

                update_kwargs: dict[str, Any] = {
                    "output": out,
                    "metadata": meta,
                }
                if model_name:
                    update_kwargs["model"] = model_name
                if temperature is not None:
                    update_kwargs["model_parameters"] = {"temperature": temperature}
                if tot_tokens > 0 or p_tokens > 0 or c_tokens > 0:
                    update_kwargs["usage_details"] = {
                        "input": p_tokens,
                        "output": c_tokens,
                        "total": tot_tokens,
                    }

                span.update(**update_kwargs)
                span.end()
            except Exception as update_exc:
                logger.warning("Lỗi kết thúc child span: %s", update_exc)


def trace_stream(name: str, question: str, tokens: Iterator[str]) -> Iterator[str]:
    """Bọc quanh answer dạng stream: trace toàn bộ output ghép lại sau
    khi stream kết thúc. Fail-safe khi Langfuse down."""
    if not settings.monitoring_enabled:
        yield from tokens
        return

    start = time.perf_counter()
    chunks: list[str] = []
    try:
        for token in tokens:
            chunks.append(token)
            yield token
    finally:
        try:
            langfuse = _get_langfuse()
            span = langfuse.start_observation(
                name=name,
                input=question,
                output="".join(chunks),
                metadata={"latency_s": time.perf_counter() - start, "streamed": True},
            )
            span.end()
            langfuse.flush()
        except Exception as exc:
            logger.warning("Lỗi ghi nhận stream trace (fail-safe active): %s", exc)
