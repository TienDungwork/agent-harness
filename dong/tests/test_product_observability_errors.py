"""Product test suite for Observability & Error Handling: Langfuse tracing, Trace caching & metrics telemetry, Error state acceptance & LLM/DB resilience."""
from __future__ import annotations

# ==============================================================================
# --- Sourced from test_trace_cache.py ---
# ==============================================================================

"""Unit tests for Phase 5: Langfuse Observability & Token Metrics."""


from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.llm.schemas import QueryResult

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
                "input": {
                    "question": "Hôm nay có bao nhiêu lượt xe vào?",
                    "columns": ["direction", "so_luot"],
                    "rows": [{"direction": "IN", "so_luot": 1956}],
                    "row_count": 1,
                },
                "output": {
                    "answer_vi": "Hôm nay có 1956 lượt xe vào.",
                    "answer_source": "llm_text",
                },
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
    assert update_kwargs["input"]["row_count"] == 1
    assert update_kwargs["output"]["answer_vi"] == "Hôm nay có 1956 lượt xe vào."
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
                "input": {"question": "Hôm nay có bao nhiêu lượt xe vào?"},
                "output": {"rewritten": {"text": "Thống kê xe IN hôm nay"}},
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
    assert update_kwargs["input"]["question"] == "Hôm nay có bao nhiêu lượt xe vào?"
    assert update_kwargs["output"]["rewritten"]["text"] == "Thống kê xe IN hôm nay"


def test_graph_node_nested_substeps(monkeypatch):
    """Substep agent/tool lồng dưới span graph node (Langfuse tree)."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_root = MagicMock()
    mock_node_span = MagicMock()
    mock_tool = MagicMock()
    mock_agent = MagicMock()
    mock_root.start_observation.return_value = mock_node_span
    mock_node_span.start_observation.side_effect = [mock_tool, mock_agent]

    def fake_generate(state):
        from src.monitoring.tracing import trace_substep

        with trace_substep("build_prompt", kind="tool", input={"question": state["question"]}) as sub:
            sub["output"] = {"user_prompt_len": 42}
        with trace_substep("generate_sql", kind="agent", input={"user_prompt_len": 42}) as sub:
            sub["output"] = {"text_len": 10}
        return {
            "sql": "SELECT 1",
            "events": [{
                "node_id": "generate_sql",
                "input": {"question": state["question"]},
                "output": {"sql": "SELECT 1"},
                "meta": {},
            }],
        }

    with patch("src.monitoring.tracing._get_langfuse"):
        from src.agent.graph import _wrap_node

        wrapped = _wrap_node("generate_sql", fake_generate)
        wrapped({"question": "Hôm nay có bao nhiêu xe?", "_trace_span": mock_root})

    mock_root.start_observation.assert_called_once()
    assert mock_node_span.start_observation.call_count == 2
    names = [c[1]["name"] for c in mock_node_span.start_observation.call_args_list]
    assert names == ["tool:build_prompt", "agent:generate_sql"]
    mock_tool.end.assert_called_once()
    mock_agent.end.assert_called_once()


def test_validate_and_repair_sql_nested_validate_substep(monkeypatch):
    """Orchestrator helper validate_and_repair_sql cũng ghi tool:validate_sql substep."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_parent = MagicMock()
    mock_validate = MagicMock()

    from src.monitoring.tracing import trace_active_parent

    with trace_active_parent(mock_parent):
        from src.agent.validate_sql import validate_and_repair_sql

        from src.db.validator import ValidationResult

        with patch("src.agent.validate_sql.validate_sql", return_value=ValidationResult(ok=True)):
            mock_parent.start_observation.return_value = mock_validate
            validate_and_repair_sql("SELECT 1", "test", user_id="u1", session_id="s1")

    mock_parent.start_observation.assert_called_once()
    assert mock_parent.start_observation.call_args[1]["name"] == "tool:validate_sql"
    mock_validate.end.assert_called_once()


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
    assert ev["output"]["answer_vi"]
    assert ev["output"]["stat_answer"]["answer_vi"]
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
from src.memory.ttl_cache import clear_ttl_cache

def test_cache_miss_then_hit_skips_run_agent(monkeypatch):
    from src.agent.graph import Agent_Output
    from src.llm.schemas import QueryResult

    mock_run_agent = MagicMock()
    valid_answer = "Hôm nay có tổng cộng 100 chiếc xe các loại vào cổng KCN."
    dummy_out = Agent_Output(question="Thống kê xe hôm nay", answer=valid_answer, query=QueryResult(tool="t", columns=["total"], rows=[[100]], row_count=1))
    mock_run_agent.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run_agent)
    monkeypatch.setattr("src.main.settings.cache_enabled", True)
    monkeypatch.setattr("src.main.settings.memory_ttl_seconds", 300)
    
    # clear cache
    clear_ttl_cache()

    # miss
    resp1 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1
    assert valid_answer in resp1.answer

    # hit
    resp2 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1 # still 1
    assert valid_answer in resp2.answer
    assert resp2.detail.get("cache_hit") is True

def test_cache_expired_entry_misses(monkeypatch):
    from src.agent.graph import Agent_Output
    from src.llm.schemas import QueryResult

    mock_run_agent = MagicMock()
    valid_answer = "Hôm nay có tổng cộng 100 chiếc xe các loại vào cổng KCN."
    dummy_out = Agent_Output(question="Thống kê xe hôm nay", answer=valid_answer, query=QueryResult(tool="t", columns=["total"], rows=[[100]], row_count=1))
    mock_run_agent.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run_agent)
    monkeypatch.setattr("src.main.settings.cache_enabled", True)
    monkeypatch.setattr("src.main.settings.memory_ttl_seconds", 300)
    
    # clear cache
    clear_ttl_cache()

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
    from src.llm.schemas import QueryResult

    mock_run_agent = MagicMock()
    valid_answer = "Hôm nay có tổng cộng 100 chiếc xe các loại vào cổng KCN."
    dummy_out = Agent_Output(question="Thống kê xe hôm nay", answer=valid_answer, query=QueryResult(tool="t", columns=["total"], rows=[[100]], row_count=1))
    mock_run_agent.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run_agent)
    monkeypatch.setattr("src.main.settings.cache_enabled", False)
    monkeypatch.setattr("src.main.settings.memory_ttl_seconds", 300)
    
    # clear cache
    clear_ttl_cache()

    # first call
    resp1 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 1
    assert valid_answer in resp1.answer

    # second call, should not hit cache
    resp2 = chat(ChatRequest(question="Thống kê xe hôm nay"))
    assert mock_run_agent.call_count == 2
    assert valid_answer in resp2.answer


def test_every_graph_node_emits_full_input_output_and_session_user_meta():
    """Tất cả node trong graph đều ghi nhận đầy đủ input, output và metadata session/user."""
    from src.agent.graph import Agent_Input, run_agent_stream

    user_id = "user-trace-full"
    session_id = "session-trace-full"

    # 1. Query data pipeline
    inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?", user_id=user_id)
    events = list(run_agent_stream(inp, session_id=session_id, user_id=user_id))

    done_events = [ev for ev in events if ev.get("status") == "done" and ev.get("node_id") not in ("__answer__", "error")]
    assert len(done_events) >= 6

    for ev in done_events:
        node_id = ev.get("node_id")
        assert ev.get("input") is not None, f"Node {node_id} thiếu input"
        assert ev.get("output") is not None, f"Node {node_id} thiếu output"
        out = ev.get("output")
        assert out is not None and out != "" and out != {}, f"Node {node_id} output bị rỗng"
        assert isinstance(ev.get("input"), dict), f"Node {node_id} input phải là dict structured"
        assert isinstance(out, dict), f"Node {node_id} output phải là dict structured"

    execute_ev = next(ev for ev in done_events if ev.get("node_id") in ("execute", "execute_sql"))
    assert "sql" in execute_ev["input"]
    assert "rows" in execute_ev["output"]
    assert "row_count" in execute_ev["output"]
    assert "Trả về" not in str(execute_ev["output"])

    # 2. Docs pipeline
    inp_docs = Agent_Input(question="Làm sao để thêm camera trên AIOC?", user_id=user_id)
    events_docs = list(run_agent_stream(inp_docs, session_id=session_id, user_id=user_id))
    docs_done = [ev for ev in events_docs if ev.get("status") == "done" and ev.get("node_id") in ("retrieve_docs", "answer_from_docs")]
    assert len(docs_done) == 2
    for ev in docs_done:
        assert ev.get("input")
        assert ev.get("output")


def test_trace_observation_receives_session_and_user_metadata(monkeypatch):
    """Langfuse start_observation nhận đầy đủ session_id và user_id từ API."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", True)

    mock_langfuse = MagicMock()
    mock_parent_span = MagicMock()
    mock_child_span = MagicMock()

    mock_langfuse.start_observation.return_value = mock_parent_span
    mock_parent_span.start_observation.return_value = mock_child_span

    with patch("src.monitoring.tracing._get_langfuse", return_value=mock_langfuse):
        from src.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/api/chat",
            json={
                "question": "Hôm nay có bao nhiêu xe vào?",
                "session_id": "sess-langfuse-test",
                "user_id": "user-langfuse-test",
            },
        )
        assert resp.status_code == 200

    # Kiểm tra start_observation của root span nhận session_id và user_id
    assert mock_langfuse.start_observation.called
    call_kwargs = mock_langfuse.start_observation.call_args[1]
    assert call_kwargs.get("session_id") == "sess-langfuse-test" or call_kwargs.get("metadata", {}).get("session_id") == "sess-langfuse-test"
    assert call_kwargs.get("user_id") == "user-langfuse-test" or call_kwargs.get("metadata", {}).get("user_id") == "user-langfuse-test"

    # Kiểm tra child spans cũng nhận session_id và user_id
    assert mock_parent_span.start_observation.called
    child_kwargs = mock_parent_span.start_observation.call_args[1]
    meta = child_kwargs.get("metadata", {})
    assert meta.get("user_id") == "user-langfuse-test"
    assert meta.get("session_id") == "sess-langfuse-test"




# ==============================================================================
# --- Sourced from test_phase5_error_states_acceptance.py ---
# ==============================================================================

"""Phase 5 Acceptance Tests — Validation and Error States.

Kiểm tra 5 tiêu chí của Phase 5:
1. SQL invalid / hết lần repair -> message ngắn tiếng Việt; không crash stream.
2. LLM timeout / DB fail -> message ngắn, không leak SQL/traceback.
3. Classify lỗi -> fallback an toàn, không im lặng.
4. Empty số liệu -> trả lời đúng chuẩn (chứa số "0").
5. SSE stream __answer__ trả về status error kèm thông báo thân thiện.
"""


import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Input, run_agent, run_agent_stream
from src.agent.intent import classify_intent_safe
from src.db.validator import ValidationResult
from src.guardrails import empty_stat_reply
from src.main import USER_ERROR_MAX_LEN, _format_error_message, app

client = TestClient(app)


def test_sql_repair_max_exhausted_yields_friendly_message_no_crash():
    """1. SQL invalid / hết lần repair: trả về message ngắn tiếng Việt trong stream mà không crash."""
    from src.main import _cache
    _cache.clear()
    inp = Agent_Input(question="Hôm nay có bao nhiêu xe vào?")

    # Mock validate_sql luôn trả về lỗi để hết số lần repair (settings.sql_repair_max)
    with (
        patch("src.llm.client.use_offline_tools", return_value=True),
        patch(
            "src.agent.validate_sql.validate_sql",
            return_value=ValidationResult(ok=False, reason="Cú pháp không hợp lệ"),
        ),
    ):
        res = client.post(
            "/api/agent/stream",
            json={"question": inp.question, "session_id": "test-repair-fail"},
        )

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    node_ids = [e.get("node_id") for e in events]
    assert "generate_sql" in node_ids
    assert "validate_sql" in node_ids
    assert "repair_sql" in node_ids
    assert "__answer__" in node_ids

    answer_ev = next(e for e in events if e.get("node_id") == "__answer__")
    ans_text = answer_ev.get("output", "")
    assert "Lỗi" in ans_text or "không hợp lệ" in ans_text or "Không thể" in ans_text
    assert len(ans_text) <= 300


def test_llm_timeout_and_db_fail_message_no_leak():
    """2. LLM timeout / DB fail: message ngắn thân thiện, không leak traceback hay raw SQL."""
    exc_timeout = TimeoutError("Request timed out after 30s to http://192.168.1.196:11434")
    exc_db = RuntimeError("psycopg2.OperationalError: could not connect to server 192.168.1.196 port 5432")

    msg_timeout = _format_error_message(exc_timeout)
    msg_db = _format_error_message(exc_db)

    assert len(msg_timeout) <= USER_ERROR_MAX_LEN
    assert len(msg_db) <= USER_ERROR_MAX_LEN
    assert "192.168.1.196" not in msg_timeout
    assert "192.168.1.196" not in msg_db
    assert "traceback" not in msg_timeout.lower()
    assert "traceback" not in msg_db.lower()


def test_classify_error_safe_fallback_not_silent():
    """3. Classify lỗi: fallback an toàn sang query_data, không trả về rỗng hay im lặng."""
    from src.llm.schemas import RewrittenQuestion

    q = RewrittenQuestion(text="Hôm nay có cảnh báo cháy hoặc khói không?")
    with (
        patch("src.agent.intent.use_offline_tools", return_value=False),
        patch("src.agent.intent.invoke_structured", side_effect=Exception("LLM down")),
    ):
        res = classify_intent_safe(q)

    assert res.intent in ("query_data", "docs", "chat", "out_of_scope")
    assert res.intent == "query_data"  # Domain cháy khói -> query_data fallback


def test_empty_statistical_data_contains_zero():
    """4. Empty số liệu: trả lời chuẩn tiếng Việt có chứa số '0'."""
    ans = empty_stat_reply()
    assert "0" in ans
    assert "không có" in ans.lower() or "không tìm thấy" in ans.lower()


def test_stream_error_emits_friendly_answer_status_error():
    """5. Lỗi stream phát ra __answer__ status error với câu thông báo ngắn gọn."""
    from src.main import _cache
    _cache.clear()

    with patch(
        "src.agent.graph.run_agent_stream",
        side_effect=RuntimeError("Database connection lost"),
    ):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu xe vào?"},
        )

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    answer_ev = next(e for e in events if e.get("node_id") == "__answer__")
    assert answer_ev.get("status") == "error"
    ans_text = answer_ev.get("output", "")
    assert "Lỗi" in ans_text or "không thể" in ans_text.lower()
    assert "Database connection lost" not in ans_text  # Sanitized

# ==============================================================================
# --- Sourced from test_phase5_llm_db_errors.py ---
# ==============================================================================

"""Phase 5 — Lỗi LLM/DB: message ngắn trên UI, stream không crash."""


import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import USER_ERROR_MAX_LEN, _format_error_message, _short_user_error, app

client = TestClient(app)


def test_short_user_error_truncates():
    long_msg = "x" * 300
    out = _short_user_error(long_msg)
    assert len(out) <= USER_ERROR_MAX_LEN
    assert out.endswith("…")


def test_format_error_message_no_stack_or_sql_leak():
    exc = RuntimeError("Traceback (most recent call last): SELECT * FROM secret_table")
    msg = _format_error_message(exc)
    assert "traceback" not in msg.lower()
    assert "select *" not in msg.lower()
    assert len(msg) <= USER_ERROR_MAX_LEN


@pytest.mark.parametrize(
    "exc,keyword",
    [
        (RuntimeError("clickhouse connect error: refused"), "clickhouse"),
        (RuntimeError("psycopg2.OperationalError: connection refused"), "database"),
        (TimeoutError("Request timed out"), "thời gian"),
        (RuntimeError("openai.RateLimitError: 429"), "rate limit"),
    ],
)
def test_format_error_messages_short_vietnamese(exc, keyword):
    msg = _format_error_message(exc)
    assert keyword.lower() in msg.lower()
    assert len(msg) <= USER_ERROR_MAX_LEN


def test_stream_db_error_yields_answer_not_crash(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache

    _cache.clear()
    with patch(
        "src.agent.graph.run_agent_stream",
        side_effect=RuntimeError("clickhouse connect error: connection refused"),
    ):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu lượt xe vào?"},
        )
    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))
    answer = next(ev for ev in events if ev.get("node_id") == "__answer__")
    assert answer.get("status") == "error"
    assert "clickhouse" in str(answer.get("output", "")).lower()
    assert "traceback" not in str(answer.get("output", "")).lower()


def test_stream_graph_thread_error_yields_friendly_answer(monkeypatch):
    """Lỗi trong graph thread → __answer__ error, không crash generator."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache

    _cache.clear()

    def _boom(*_args, **_kwargs):
        yield {"node_id": "recall", "status": "running"}
        raise RuntimeError("LLM API timeout after 30s")

    with patch("src.agent.graph.run_agent_stream", side_effect=_boom):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu xe vào?"},
        )
    assert res.status_code == 200
    assert "__answer__" in res.text
    assert "mô hình ai" in res.text.lower() or "thời gian" in res.text.lower()


def test_frontend_stream_error_handling_wiring():
    res = client.get("/app.js")
    js = res.text if res.status_code == 200 else open("frontend/app.js", encoding="utf-8").read()
    assert "lastStreamError" in js
    assert "event.status === 'error'" in js or "event.status === \"error\"" in js
    assert "event.node_id === 'error'" in js or 'event.node_id === "error"' in js

