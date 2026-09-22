"""Unit tests for Phase 5: Langfuse Observability & Token Metrics."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agent.tools import QueryResult

from src.monitoring.tracing import (
    extract_token_usage,
    trace_answer,
    trace_step,
    trace_stream,
)
from src.monitoring.tracing import (
    extract_token_usage as be_extract_token_usage,
    trace_answer as be_trace_answer,
    trace_step as be_trace_step,
)


def test_extract_token_usage_from_usage_metadata():
    msg = AIMessage(content="Hello", usage_metadata={"input_tokens": 42, "output_tokens": 18, "total_tokens": 60})
    usage = extract_token_usage(msg)
    assert usage == {"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60}


def test_extract_token_usage_from_response_metadata():
    msg = AIMessage(
        content="Hello",
        response_metadata={"token_usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}},
    )
    usage = extract_token_usage(msg)
    assert usage == {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}


def test_extract_token_usage_from_dict():
    data = {"usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}}
    usage = extract_token_usage(data)
    assert usage == {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}


def test_extract_token_usage_empty_returns_zeroes():
    assert extract_token_usage(None) == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    assert extract_token_usage("") == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_tracing_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    with trace_answer("chat", "test question") as t:
        t["output"] = {"status": "ok", "answer": "Test answer"}
        assert t.get("_span") is None

    with trace_step(None, "chon_tool", input="test question") as step:
        step["output"] = {"tool": "count_vehicle_flow"}
        assert step.get("_span") is None

    tokens = list(trace_stream("stream", "test", iter(["hello", "world"])))
    assert tokens == ["hello", "world"]


def test_trace_answer_and_trace_step_with_langfuse(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)
    monkeypatch.setattr("src.monitoring.tracing.settings.llm_backend", "openai")
    monkeypatch.setattr("src.monitoring.tracing.settings.llm_model", "gpt-4o-mini")
    monkeypatch.setattr("src.monitoring.tracing.settings.llm_temperature", 0.0)

    mock_langfuse = MagicMock()
    mock_parent_span = MagicMock()
    mock_child_span = MagicMock()

    mock_langfuse.start_observation.return_value = mock_parent_span
    mock_parent_span.start_observation.return_value = mock_child_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        # 1. Trace cha (chat)
        with trace_answer("chat", "Có bao nhiêu xe vào hôm nay?", metadata={"endpoint": "/api/chat"}) as parent_box:
            assert parent_box["_span"] is mock_parent_span

            # 2. Trace con (chon_tool)
            with trace_step(parent_box["_span"], "chon_tool", input="Có bao nhiêu xe vào hôm nay?") as child_box:
                child_box["output"] = {"tool_calls": [{"name": "count_vehicle_flow", "args": {}}]}
                child_box["usage"] = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
                child_box["model_name"] = "gpt-4o-mini"

            parent_box["output"] = {"status": "ok", "answer": "Hôm nay có 150 lượt xe vào."}
            parent_box["usage"] = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}

    # Verify parent span calls
    mock_langfuse.start_observation.assert_called_once()
    assert mock_parent_span.update.called
    update_kwargs = mock_parent_span.update.call_args[1]
    assert update_kwargs["output"] == {"status": "ok", "answer": "Hôm nay có 150 lượt xe vào."}
    assert update_kwargs["metadata"]["prompt_tokens"] == 100
    assert update_kwargs["metadata"]["completion_tokens"] == 20
    assert update_kwargs["metadata"]["total_tokens"] == 120
    assert update_kwargs["metadata"]["model_name"] == "gpt-4o-mini"
    assert "latency_s" in update_kwargs["metadata"]
    assert update_kwargs["usage_details"] == {"input": 100, "output": 20, "total": 120}
    mock_parent_span.end.assert_called_once()
    mock_langfuse.flush.assert_called_once()

    # Verify child span calls
    mock_parent_span.start_observation.assert_called_once()
    assert mock_child_span.update.called
    child_update_kwargs = mock_child_span.update.call_args[1]
    assert child_update_kwargs["output"] == {"tool_calls": [{"name": "count_vehicle_flow", "args": {}}]}
    assert child_update_kwargs["metadata"]["prompt_tokens"] == 100
    assert child_update_kwargs["metadata"]["model_name"] == "gpt-4o-mini"
    assert "latency_s" in child_update_kwargs["metadata"]
    assert child_update_kwargs["usage_details"] == {"input": 100, "output": 20, "total": 120}
    mock_child_span.end.assert_called_once()


def test_trace_answer_exception_handling(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_span = MagicMock()
    mock_langfuse.start_observation.return_value = mock_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        with pytest.raises(ValueError, match="Database error"):
            with trace_answer("chat", "invalid query") as t:
                raise ValueError("Database error")

    mock_span.update.assert_any_call(level="ERROR", status_message="Database error")
    mock_span.end.assert_called_once()
    mock_langfuse.flush.assert_called_once()


def test_trace_answer_failsafe_when_langfuse_init_fails(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    with patch("src.monitoring.tracing._get_langfuse", side_effect=ConnectionRefusedError("Langfuse server down")):
        with trace_answer("chat", "Có bao nhiêu xe?") as t:
            t["output"] = {"answer": "Có 10 xe"}
            assert t.get("_span") is None


def test_trace_answer_failsafe_when_start_observation_fails(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_langfuse.start_observation.side_effect = TimeoutError("Observation timeout")

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        with trace_answer("chat", "Có bao nhiêu xe?") as t:
            t["output"] = {"answer": "Có 10 xe"}
            assert t.get("_span") is None


def test_trace_answer_failsafe_when_flush_fails(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_span = MagicMock()
    mock_langfuse.start_observation.return_value = mock_span
    mock_langfuse.flush.side_effect = RuntimeError("Network partition on flush")

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        with trace_answer("chat", "Có bao nhiêu xe?") as t:
            t["output"] = {"answer": "Có 10 xe"}
            assert t.get("_span") is mock_span

    mock_span.end.assert_called_once()


def test_trace_step_failsafe_when_child_observation_fails():
    mock_parent = MagicMock()
    mock_parent.start_observation.side_effect = RuntimeError("Child span creation error")

    with trace_step(mock_parent, "chon_tool", input="Có bao nhiêu xe?") as step:
        step["output"] = {"tool": "count_vehicle_flow"}
        assert step.get("_span") is None


def test_full_pipeline_trace_step_tree(monkeypatch):
    """Kiểm tra toàn bộ cây span ReAct: trace cha (chat) -> chon_tool -> chay_tool -> dien_giai."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_parent = MagicMock()
    mock_span_chon = MagicMock()
    mock_span_chay = MagicMock()
    mock_span_dien = MagicMock()

    mock_langfuse.start_observation.return_value = mock_parent
    mock_parent.start_observation.side_effect = [mock_span_chon, mock_span_chay, mock_span_dien]

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        with trace_answer("chat", "Biển số 65A-123.45 xuất hiện ở đâu?") as parent:
            # Step 1: Chọn tool
            with trace_step(parent["_span"], "chon_tool", input="Biển số 65A-123.45") as s1:
                s1["output"] = {"tool_calls": [{"name": "trace_plate", "args": {"plate_text": "65A12345"}}]}
                s1["usage"] = {"prompt_tokens": 150, "completion_tokens": 30, "total_tokens": 180}
            
            # Step 2: Chạy tool
            with trace_step(parent["_span"], "chay_tool", input="trace_plate") as s2:
                s2["output"] = {"tools": ["trace_plate"]}
            
            # Step 3: Diễn giải
            with trace_step(parent["_span"], "dien_giai", input="kết quả") as s3:
                s3["output"] = {"answer": "Xe xuất hiện tại Cổng 1 lúc 08:30.", "tools": "trace_plate"}

            parent["output"] = {"status": "ok", "answer": "Xe xuất hiện tại Cổng 1 lúc 08:30."}
            parent["usage"] = {"prompt_tokens": 150, "completion_tokens": 30, "total_tokens": 180}

    # Verify calls
    assert mock_parent.start_observation.call_count == 3
    mock_span_chon.end.assert_called_once()
    mock_span_chay.end.assert_called_once()
    mock_span_dien.end.assert_called_once()
    mock_parent.end.assert_called_once()
    mock_langfuse.flush.assert_called_once()



def test_trace_answer_with_self_hosted_metadata(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)
    monkeypatch.setattr("src.monitoring.tracing.settings.llm_backend", "self_hosted")
    monkeypatch.setattr("src.monitoring.tracing.settings.model_name", "qwen3-4b")

    mock_langfuse = MagicMock()
    mock_span = MagicMock()
    mock_langfuse.start_observation.return_value = mock_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        with trace_answer("chat", "Thống kê xe") as t:
            t["output"] = {"answer": "100 xe"}

    update_kwargs = mock_span.update.call_args[1]
    assert update_kwargs["model"] == "qwen3-4b"
    assert update_kwargs["metadata"]["model_name"] == "qwen3-4b"


def test_trace_answer_custom_temperature_and_model_override(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_span = MagicMock()
    mock_langfuse.start_observation.return_value = mock_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        with trace_answer("chat", "Thống kê") as t:
            t["model_name"] = "qwen3-4b-custom"
            t["temperature"] = 0.5
            t["output"] = {"answer": "ok"}

    update_kwargs = mock_span.update.call_args[1]
    assert update_kwargs["model"] == "qwen3-4b-custom"
    assert update_kwargs["model_parameters"]["temperature"] == 0.5


def test_trace_step_exception_handling():
    mock_parent = MagicMock()
    mock_child = MagicMock()
    mock_parent.start_observation.return_value = mock_child

    with pytest.raises(RuntimeError, match="SQL error"):
        with trace_step(mock_parent, "chay_tool", input="query") as s:
            raise RuntimeError("SQL error")

    mock_child.update.assert_any_call(level="ERROR", status_message="SQL error")
    mock_child.end.assert_called_once()


def test_trace_stream_with_langfuse(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_span = MagicMock()
    mock_langfuse.start_observation.return_value = mock_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        tokens = list(trace_stream("stream_test", "câu hỏi", iter(["Hôm ", "nay ", "có ", "10 xe"])))
        assert "".join(tokens) == "Hôm nay có 10 xe"

    mock_langfuse.start_observation.assert_called_once()
    obs_kwargs = mock_langfuse.start_observation.call_args[1]
    assert obs_kwargs["output"] == "Hôm nay có 10 xe"
    assert obs_kwargs["metadata"]["streamed"] is True
    mock_span.end.assert_called_once()
    mock_langfuse.flush.assert_called_once()


def test_v5_graph_trace_step_uses_node_event_input(monkeypatch):
    """Langfuse child span input/output lấy từ event node, không lặp câu hỏi gốc."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_parent = MagicMock()
    mock_child = MagicMock()
    mock_langfuse.start_observation.return_value = mock_parent
    mock_parent.start_observation.return_value = mock_child

    captured: list[dict] = []

    def fake_respond(_state):
        return {
            "result": None,
            "events": [{
                "node_id": "respond",
                "input": "1 rows | cols=['direction', 'so_luot']",
                "output": "Hôm nay có 1956 lượt xe vào.",
                "meta": {"llm_used": True, "answer_source": "llm_text"},
            }],
        }

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        from src.agent.graph import _wrap_node

        wrapped = _wrap_node("respond", fake_respond)
        wrapped({"question": "Hôm nay có bao nhiêu lượt xe vào?", "_trace_span": mock_parent})

    mock_parent.start_observation.assert_called_once()
    child_kwargs = mock_parent.start_observation.call_args[1]
    assert child_kwargs["name"] == "respond"
    assert child_kwargs.get("input") is None

    update_kwargs = mock_child.update.call_args[1]
    assert update_kwargs["input"] == "1 rows | cols=['direction', 'so_luot']"
    assert "1956" in str(update_kwargs["output"])
    assert update_kwargs["metadata"]["answer_source"] == "llm_text"


def test_v5_graph_trace_rewrite_input_not_parent_question(monkeypatch):
    """Span rewrite phải ghi input câu gốc, không lặp question đã rewrite trong state."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_parent = MagicMock()
    mock_child = MagicMock()
    mock_langfuse = MagicMock()
    mock_langfuse.start_observation.return_value = mock_parent
    mock_parent.start_observation.return_value = mock_child

    def fake_rewrite(state):
        return {
            "rewritten": None,
            "question": "Thống kê xe IN hôm nay",
            "events": [{
                "node_id": "rewrite",
                "input": "Hôm nay có bao nhiêu lượt xe vào?",
                "output": '{"text":"Thống kê xe IN hôm nay"}',
                "meta": {"llm_used": True},
            }],
        }

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        from src.agent.graph import _wrap_node

        wrapped = _wrap_node("rewrite", fake_rewrite)
        wrapped({
            "question": "Hôm nay có bao nhiêu lượt xe vào?",
            "_trace_span": mock_parent,
        })

    update_kwargs = mock_child.update.call_args[1]
    assert update_kwargs["input"] == "Hôm nay có bao nhiêu lượt xe vào?"
    assert "Thống kê xe IN hôm nay" in str(update_kwargs["output"])


def test_strip_thinking_removes_qwen_block():
    from src.agent.graph import _strip_thinking

    raw = "\x3cthink\x3einternal\x3c/think\x3e\nHôm nay có 10 xe vào."
    assert _strip_thinking(raw) == "Hôm nay có 10 xe vào."


def test_respond_offline_emits_stat_answer_event():
    from src.agent.graph import respond_node

    out = respond_node({
        "question": "Hôm nay có bao nhiêu lượt xe vào?",
        "rows": [{"direction": "IN", "so_luot": 10}],
        "columns": ["direction", "so_luot"],
    })
    ev = out["events"][0]
    assert "answer_vi" in ev["output"]
    assert ev["meta"]["stat_answer"]["answer_vi"]
    assert out["result"].answer


def test_backend_monitoring_reexport():
    assert be_extract_token_usage is extract_token_usage
    assert be_trace_answer is trace_answer
    assert be_trace_step is trace_step


def test_trace_answer_token_sum_via_contextvar(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_span = MagicMock()
    mock_langfuse.start_observation.return_value = mock_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        from src.monitoring.tracing import add_request_tokens
        with trace_answer("chat", "test sum tokens") as t:
            # Mô phỏng gọi LLM 2 lần
            add_request_tokens({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
            add_request_tokens({"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30})

            t["output"] = {"answer": "done"}

    update_kwargs = mock_span.update.call_args[1]
    assert update_kwargs["metadata"]["prompt_tokens"] == 30
    assert update_kwargs["metadata"]["completion_tokens"] == 15
    assert update_kwargs["metadata"]["total_tokens"] == 45
    assert update_kwargs["usage_details"] == {"input": 30, "output": 15, "total": 45}


from src.main import _cache, chat, ChatRequest

def test_cache_miss_then_hit_skips_run_agent(monkeypatch):
    from src.agent.graph import Agent_Output
    from src.agent.tools import QueryResult

    mock_run_agent = MagicMock()
    valid_answer = "Hôm nay có tổng cộng 100 chiếc xe các loại vào cổng KCN."
    dummy_out = Agent_Output(question="Thống kê xe hôm nay", answer=valid_answer, query=QueryResult(tool="t", columns=["total"], rows=[[100]], row_count=1))
    mock_run_agent.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run_agent)
    monkeypatch.setattr("src.main.settings.cache_enabled", True)
    monkeypatch.setattr("src.main.settings.cache_ttl_s", 60)
    
    # clear cache
    _cache.clear()

    # miss
    resp1 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1
    assert valid_answer in resp1.answer

    # hit
    resp2 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1 # still 1
    assert valid_answer in resp2.answer

def test_cache_expired_entry_misses(monkeypatch):
    from src.agent.graph import Agent_Output
    from src.agent.tools import QueryResult

    mock_run_agent = MagicMock()
    valid_answer = "Hôm nay có tổng cộng 100 chiếc xe các loại vào cổng KCN."
    dummy_out = Agent_Output(question="Thống kê xe hôm nay", answer=valid_answer, query=QueryResult(tool="t", columns=["total"], rows=[[100]], row_count=1))
    mock_run_agent.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run_agent)
    monkeypatch.setattr("src.main.settings.cache_enabled", True)
    monkeypatch.setattr("src.main.settings.cache_ttl_s", 60)
    
    # clear cache
    _cache.clear()

    # miss 1
    resp1 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1
    assert valid_answer in resp1.answer

    # expire cache manually
    key = list(_cache.keys())[0]
    _cache[key]["expire_at"] = 0

    # miss 2
    resp2 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 2
    assert valid_answer in resp2.answer

def test_cache_disabled(monkeypatch):
    from src.agent.graph import Agent_Output
    from src.agent.tools import QueryResult

    mock_run_agent = MagicMock()
    valid_answer = "Hôm nay có tổng cộng 100 chiếc xe các loại vào cổng KCN."
    dummy_out = Agent_Output(question="Thống kê xe hôm nay", answer=valid_answer, query=QueryResult(tool="t", columns=["total"], rows=[[100]], row_count=1))
    mock_run_agent.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run_agent)
    monkeypatch.setattr("src.main.settings.cache_enabled", False)
    monkeypatch.setattr("src.main.settings.cache_ttl_s", 60)
    
    # clear cache
    _cache.clear()

    # first call
    resp1 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1
    assert valid_answer in resp1.answer

    # second call, should not hit cache
    resp2 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 2
    assert valid_answer in resp2.answer

