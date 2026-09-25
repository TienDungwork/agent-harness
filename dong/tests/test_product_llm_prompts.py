"""Product test suite for LLM & Prompts: Multi-backend connectivity (self_hosted/Ollama/OpenAI), Prompt template registry & variable formatting, Structured output schemas."""
from __future__ import annotations

# ==============================================================================
# --- Sourced from test_llm.py ---
# ==============================================================================

"""Unit tests for Dual LLM backend integration (OpenAI & Self-hosted Qwen3-4B)."""


import pytest
from langchain_openai import ChatOpenAI

from src.llm import (
    _BACKENDS,
    _RotatingKeyPool,
    base_llm,
    use_offline_tools,
)
from src.config import settings


def test_backends_registry_contains_required_providers():
    """Kiểm tra registry chứa đầy đủ 'openai' và 'self_hosted'."""
    assert "openai" in _BACKENDS
    assert "self_hosted" in _BACKENDS
    assert _BACKENDS["self_hosted"].default_base_url == "http://192.168.1.196:18083/v1"
    assert _BACKENDS["self_hosted"].requires_real_key is False


def test_base_llm_self_hosted_configuration(monkeypatch):
    """Kiểm tra khởi tạo ChatOpenAI cho model tự host qwen3-4b."""
    monkeypatch.setattr(settings, "llm_backend", "self_hosted")
    monkeypatch.setattr(settings, "model_base_url", "http://192.168.1.196:18083/v1")
    monkeypatch.setattr(settings, "model_name", "qwen3-4b")
    monkeypatch.setattr(settings, "model_api_key", "test-qwen-key")

    llm = base_llm(backend_override="self_hosted")
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "qwen3-4b"
    assert str(llm.openai_api_base).rstrip("/") == "http://192.168.1.196:18083/v1"
    assert llm.openai_api_key.get_secret_value() == "test-qwen-key"


def test_base_llm_openai_cloud_configuration(monkeypatch):
    """Kiểm tra khởi tạo ChatOpenAI cho OpenAI Cloud gpt-4o-mini."""
    monkeypatch.setattr(settings, "openai_api_keys", "sk-proj-test1,sk-proj-test2")
    from src.llm import _pool
    _pool.cache_clear()

    llm = base_llm(backend_override="openai")
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o-mini"
    assert llm.openai_api_key.get_secret_value() in ["sk-proj-test1", "sk-proj-test2"]


def test_base_llm_invalid_backend_raises_value_error():
    """Backend không hợp lệ raise ValueError."""
    with pytest.raises(ValueError, match="không hợp lệ"):
        base_llm(backend_override="unsupported_provider")


def test_rotating_key_pool_round_robin_and_cooldown():
    """Kiểm tra key pool xoay vòng và cooldown khi gặp rate limit."""
    keys = ["key-1", "key-2", "key-3"]
    pool = _RotatingKeyPool(keys)

    # Round-robin
    first = pool.get_key()
    second = pool.get_key()
    third = pool.get_key()
    assert {first, second, third} == {"key-1", "key-2", "key-3"}

    # Đưa key-1 vào cooldown 60s
    pool.mark_limited("key-1", cooldown_seconds=60.0)

    # Lượt lấy tiếp theo không được trả về key-1 nếu còn key khác khả dụng
    retrieved = [pool.get_key() for _ in range(4)]
    assert "key-1" not in retrieved

from pathlib import Path

import pytest

from src.prompts import PromptRegistry, registry


def test_prompt_registry_default_dir_is_resource():
    reg = PromptRegistry()
    assert "resource" in reg.prompts_dir.parts
    assert reg.prompts_dir.as_posix().endswith("resource/prompts")
    assert reg.prompts_dir.is_dir()


def test_prompt_registry_get_by_version():
    reg = registry()
    prompt = reg.get("sql_agent", 1)
    assert prompt.name == "sql_agent"
    assert prompt.version == 1
    assert "PostgreSQL" in prompt.template


def test_prompt_registry_get_classify_production():
    reg = registry()
    prompt = reg.get("classify", "production")
    assert prompt.name == "classify"
    assert "Phân loại ý định câu người dùng" in prompt.template


def test_prompt_registry_render_success():
    reg = registry()
    rendered = reg.render("sql_agent", "production")
    assert "PostgreSQL" in rendered
    assert "SELECT" in rendered


def test_prompt_registry_non_existent_prompt_raises_file_not_found():
    reg = registry()
    with pytest.raises(FileNotFoundError):
        reg.get("non_existent_prompt", 1)


ALL_PROMPT_NAMES = [
    "answer_docs",
    "classify",
    "judge_eval",
    "memory_extract",
    "orchestrator",
    "plan_chart",
    "respond_stat",
    "rewrite",
    "sql_agent",
]


@pytest.mark.parametrize("prompt_name", ALL_PROMPT_NAMES)
def test_each_prompt_name_loads(prompt_name: str):
    """Kiểm tra từng prompt name trong resource/prompts/ load thành công qua registry."""
    reg = registry()
    prompt = reg.get(prompt_name, "production")
    assert prompt.name == prompt_name
    assert prompt.version >= 1
    assert len(prompt.template.strip()) > 0


def test_render_missing_var_raises_value_error_for_prompt_with_vars(monkeypatch):
    """Kiểm tra render prompt có chứa biến khi thiếu biến sẽ raise ValueError."""
    from unittest.mock import patch
    from src.prompts.registry import Prompt

    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_vars", version=1, template="Xin chào {now}, user là {user}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_vars")
        assert "test_vars" in str(exc_info.value)
        assert "thiếu biến" in str(exc_info.value).lower()
        assert "now" in str(exc_info.value)


def test_api_llm_ping_returns_metadata():
    """Kiểm tra GET /api/llm/ping trả về {status, backend, model, base_url}."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from src.main import app

    tc = TestClient(app)
    with patch("src.main.llm_ping", return_value="OK"):
        res = tc.get("/api/llm/ping")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "OK"
        assert data["backend"] == settings.llm_backend
        assert data["model"] == settings.effective_model
        assert "base_url" in data



# ==============================================================================
# --- Sourced from test_structured.py ---
# ==============================================================================

"""Offline tests — invoke_structured + Pydantic schemas (không gọi LAN)."""


import base64
import pytest
from pydantic import ValidationError

from src.chart import plan_chart, render_chart, should_render_chart
from src.llm.schemas import (
    ChartSpec,
    DocsAnswer,
    IntentResult,
    QueryPlan,
    RewrittenQuestion,
    StatAnswer,
)
from src.llm.structured import invoke_structured


def test_rewritten_question_schema_defaults():
    q = RewrittenQuestion(text="đếm xe hôm nay")
    assert q.text == "đếm xe hôm nay"
    assert q.filters == []
    assert q.time_range is None


def test_intent_result_rejects_invalid_intent():
    with pytest.raises(ValidationError):
        IntentResult(intent="weather", reason="x")


def test_query_plan_and_stat_chart_schemas():
    plan = QueryPlan(tables=["vehicle_events"], selects=["count(*)"], filters=["vehicle_type=car"], limit=10)
    assert plan.group_by == []
    assert plan.limit == 10

    docs = DocsAnswer(answer_vi="Mở menu Camera", card_ids=["how_to_add_cam"], steps=["B1", "B2"])
    assert docs.steps == ["B1", "B2"]

    stat = StatAnswer(answer_vi="Có 12 xe", highlights=["12"], chart_requested=True)
    assert stat.chart_requested is True

    chart = ChartSpec(chart_type="bar", x_column="loai", y_column="so_luong", title_vi="Lượt xe")
    assert chart.chart_type == "bar"


def test_invoke_structured_mock_returns_schema(monkeypatch):
    expected = IntentResult(intent="how_to", reason="hỏi cách dùng")

    class _FakeStructured:
        def invoke(self, messages):
            assert messages
            return expected

    class _FakeLLM:
        def with_structured_output(self, schema):
            assert schema is IntentResult
            return _FakeStructured()

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    result = invoke_structured(
        [{"role": "user", "content": "làm sao thêm camera?"}],
        IntentResult,
    )
    assert result == expected
    assert result.intent == "how_to"


def test_invoke_structured_coerces_dict_to_schema(monkeypatch):
    class _FakeStructured:
        def invoke(self, messages):
            return {
                "text": "đếm xe IN hôm nay",
                "filters": ["direction=IN"],
                "time_range": "today",
                "intent_hint": "query_data",
            }

    class _FakeLLM:
        def with_structured_output(self, schema):
            return _FakeStructured()

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    result = invoke_structured([{"role": "user", "content": "xe vào hôm nay"}], RewrittenQuestion)
    assert isinstance(result, RewrittenQuestion)
    assert result.filters == ["direction=IN"]
    assert result.intent_hint == "query_data"


def test_invoke_structured_validation_error_is_clear(monkeypatch):
    class _FakeStructured:
        def invoke(self, messages):
            return {"intent": "weather", "reason": "x"}

    class _FakeLLM:
        def with_structured_output(self, schema):
            return _FakeStructured()

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    with pytest.raises(RuntimeError, match="không khớp schema IntentResult"):
        invoke_structured([{"role": "user", "content": "trời mưa?"}], IntentResult)


def test_invoke_structured_llm_failure_is_clear(monkeypatch):
    class _FakeLLM:
        def with_structured_output(self, schema):
            raise ConnectionError("refused")

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    with pytest.raises(RuntimeError, match="Lỗi LLM structured"):
        invoke_structured([{"role": "user", "content": "hi"}], RewrittenQuestion)


# --- Phase 2.5: Chart tests (render_chart, should_render_chart, plan_chart) ---


def test_render_chart_bar_success():
    """render_chart trả về chuỗi PNG base64 hợp lệ, bắt đầu bằng iVBOR và magic \x89PNG."""
    rows = [
        {"vehicle_type": "CAR", "n": 10},
        {"vehicle_type": "MOTORCYCLE", "n": 20},
        {"vehicle_type": "TRUCK", "n": 3},
    ]
    spec = ChartSpec(chart_type="bar", x_column="vehicle_type", y_column="n", title_vi="Lượt xe theo loại")
    b64 = render_chart(rows, spec)

    assert b64
    assert isinstance(b64, str)
    assert b64.startswith("iVBOR")
    raw_bytes = base64.b64decode(b64)
    assert raw_bytes.startswith(b"\x89PNG")


def test_render_chart_line_and_pie():
    """render_chart hỗ trợ chart_type line và pie."""
    rows = [
        {"vehicle_type": "CAR", "n": 10},
        {"vehicle_type": "MOTORCYCLE", "n": 20},
        {"vehicle_type": "TRUCK", "n": 5},
    ]

    # Line chart
    spec_line = ChartSpec(chart_type="line", x_column="vehicle_type", y_column="n", title_vi="Lượt xe theo thời gian")
    b64_line = render_chart(rows, spec_line)
    assert b64_line.startswith("iVBOR")
    assert base64.b64decode(b64_line).startswith(b"\x89PNG")

    # Pie chart
    spec_pie = ChartSpec(chart_type="pie", x_column="vehicle_type", y_column="n", title_vi="Tỷ lệ cơ cấu phương tiện")
    b64_pie = render_chart(rows, spec_pie)
    assert b64_pie.startswith("iVBOR")
    assert base64.b64decode(b64_pie).startswith(b"\x89PNG")


def test_render_chart_empty_rows_and_invalid_spec():
    """render_chart trả về chuỗi rỗng khi rows rỗng hoặc spec là None."""
    spec = ChartSpec(chart_type="bar", x_column="col_x", y_column="col_y", title_vi="Test")
    assert render_chart([], spec) == ""
    assert render_chart(None, spec) == ""
    assert render_chart([{"col_x": "A", "col_y": 1}], None) == ""


def test_render_chart_fallback_column_selection():
    """render_chart tự động chọn cột nếu spec thiếu cột hoặc cột không khớp."""
    rows = [
        {"loai_xe": "CAR", "so_luong": 15},
        {"loai_xe": "BUS", "so_luong": 2},
    ]
    spec_missing_cols = ChartSpec(chart_type="bar", x_column="", y_column="", title_vi="Biểu đồ")
    b64 = render_chart(rows, spec_missing_cols)
    assert b64.startswith("iVBOR")


def test_should_render_chart_keywords_true_and_false():
    """should_render_chart phát hiện đúng từ khóa vẽ biểu đồ tiếng Việt và tiếng Anh."""
    # True cases
    assert should_render_chart("Vẽ biểu đồ số lượng xe") is True
    assert should_render_chart("vẽ biểu đồ lượt xe hôm nay") is True
    assert should_render_chart("chart lượt xe theo ngày") is True
    assert should_render_chart("plot dữ liệu camera cổng 1") is True
    assert should_render_chart("Vẽ đồ thị số xe") is True
    assert should_render_chart("thống kê theo loại xe") is True
    assert should_render_chart("tỷ lệ xe máy so với ô tô") is True
    assert should_render_chart("cơ cấu phương tiện") is True
    assert should_render_chart("phân bố lưu lượng xe") is True
    assert should_render_chart("vẽ lượng xe ra vào") is True

    # False cases
    assert should_render_chart("Có bao nhiêu camera đang hoạt động?") is False
    assert should_render_chart("Làm sao thêm camera mới vào hệ thống?") is False
    assert should_render_chart("Thời tiết hôm nay thế nào?") is False
    assert should_render_chart("") is False
    assert should_render_chart(None) is False


def test_should_render_chart_with_stat_answer():
    """should_render_chart tôn trọng cờ chart_requested trong StatAnswer."""
    stat_requested = StatAnswer(answer_vi="Có 15 xe ô tô.", chart_requested=True)
    assert should_render_chart("Bao nhiêu xe?", stat_requested) is True

    stat_not_requested = StatAnswer(answer_vi="Có 15 xe ô tô.", chart_requested=False)
    assert should_render_chart("Bao nhiêu xe?", stat_not_requested) is False


def test_plan_chart_offline_heuristics():
    """plan_chart offline trích xuất đúng cột category + numeric và chart_type."""
    rows = [
        {"vehicle_type": "CAR", "so_luong": 12},
        {"vehicle_type": "TRUCK", "so_luong": 4},
    ]

    # Bar chart heuristic
    spec_bar = plan_chart(rows, "Vẽ biểu đồ lượt xe theo loại")
    assert isinstance(spec_bar, ChartSpec)
    assert spec_bar.chart_type == "bar"
    assert spec_bar.x_column == "vehicle_type"
    assert spec_bar.y_column == "so_luong"
    assert spec_bar.title_vi

    # Line chart heuristic
    spec_line = plan_chart(rows, "Lượt xe theo ngày")
    assert spec_line.chart_type == "line"

    # Pie chart heuristic
    spec_pie = plan_chart(rows, "Tỷ lệ cơ cấu phương tiện")
    assert spec_pie.chart_type == "pie"

    # Empty rows
    spec_empty = plan_chart([], "Biểu đồ")
    assert isinstance(spec_empty, ChartSpec)
    assert spec_empty.x_column == ""
    assert spec_empty.y_column == ""


def test_plan_chart_mock_structured_online(monkeypatch):
    """plan_chart gọi invoke_structured khi online và trả về ChartSpec từ LLM."""
    expected = ChartSpec(chart_type="line", x_column="ngay", y_column="luot", title_vi="Xu hướng xe")

    class _FakeStructured:
        def invoke(self, messages):
            assert messages
            return expected

    class _FakeLLM:
        def with_structured_output(self, schema):
            assert schema is ChartSpec
            return _FakeStructured()

    monkeypatch.setattr("src.chart.render.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    rows = [{"ngay": "2026-09-21", "luot": 100}]
    result = plan_chart(rows, "Vẽ xu hướng lưu lượng")
    assert result == expected
    assert result.chart_type == "line"
    assert result.x_column == "ngay"
    assert result.y_column == "luot"


def test_plan_chart_llm_failure_falls_back_to_offline(monkeypatch):
    """plan_chart tự động fallback sang offline heuristic nếu LLM structured gặp lỗi."""
    class _FakeLLM:
        def with_structured_output(self, schema):
            raise RuntimeError("LLM connection timeout")

    monkeypatch.setattr("src.chart.render.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    rows = [{"vehicle_type": "BUS", "n": 8}]
    result = plan_chart(rows, "Vẽ biểu đồ xe buýt")
    assert isinstance(result, ChartSpec)
    assert result.x_column == "vehicle_type"
    assert result.y_column == "n"


# ==============================================================================
# --- Sourced from test_phase5_prompt_vars.py ---
# ==============================================================================

"""Phase 5 — Thiếu biến prompt: lỗi rõ (không template trống).

Kiểm tra:
1. Template rỗng hoặc whitespace-only trước render -> ValueError có tên prompt.
2. Thiếu biến bắt buộc -> ValueError có tên prompt + danh sách biến thiếu tiếng Việt.
3. Render ra chuỗi rỗng -> ValueError có tên prompt.
4. Render còn placeholder chưa thay thế -> ValueError có tên prompt + placeholder.
5. Render thành công agent_system với now=...
6. _format_error_message maps prompt ValueError sang câu tiếng Việt thân thiện cho người dùng.
7. Integration: lỗi prompt trong /api/chat -> 503 friendly message.
8. Integration: lỗi prompt trong /api/agent/stream -> __answer__ error SSE friendly message.
"""


import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import USER_ERROR_MAX_LEN, _format_error_message, app
from src.prompts.registry import Prompt, PromptRegistry, registry

client = TestClient(app)


def test_empty_template_raises_value_error_with_prompt_name():
    """Template rỗng trước render phải raise ValueError kèm tên prompt."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_empty", version=1, template="")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_empty")
        err = str(exc_info.value)
        assert "test_empty" in err
        assert "template rỗng" in err.lower()


def test_whitespace_template_raises_value_error_with_prompt_name():
    """Template chỉ chứa khoảng trắng/xuống dòng phải raise ValueError kèm tên prompt."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_ws", version=1, template="  \n\t  ")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_ws")
        err = str(exc_info.value)
        assert "test_ws" in err
        assert "template rỗng" in err.lower()


def test_missing_required_var_raises_value_error_with_name_and_var():
    """Thiếu biến bắt buộc phải raise ValueError kèm tên prompt và tên biến thiếu."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_prompt_vars", version=1, template="Xin chào {now}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_prompt_vars")
        err = str(exc_info.value)
        assert "test_prompt_vars" in err
        assert "now" in err
        assert "thiếu biến" in err.lower()


def test_render_resulting_in_empty_string_raises_value_error():
    """Template sau khi render ra chuỗi rỗng phải raise ValueError."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_blank_output", version=1, template="{content}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_blank_output", content="   ")
        err = str(exc_info.value)
        assert "test_blank_output" in err
        assert "rỗng" in err.lower()


def test_unreplaced_placeholder_raises_value_error():
    """Placeholder chưa được thay thế còn sót lại trong kết quả render phải raise ValueError."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_placeholder", version=1, template="Xin chào {user}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_placeholder", user="{unreplaced_var}")
        err = str(exc_info.value)
        assert "test_placeholder" in err
        assert "placeholder" in err.lower()
        assert "unreplaced_var" in err


def test_successful_render_prompt_with_vars():
    """Render thành công prompt với tham số."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_prompt_vars", version=1, template="Thời gian là {now}")
    with patch.object(reg, "get", return_value=fake_prompt):
        rendered = reg.render("test_prompt_vars", "production", now="2026-09-22 15:30:00")
        assert "2026-09-22 15:30:00" in rendered
        assert len(rendered.strip()) > 0


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("Prompt 'agent_system' thiếu biến: ['now']"),
        ValueError("Prompt 'test_empty' có template rỗng"),
        ValueError("Prompt 'test_render' sau khi render có nội dung rỗng"),
        ValueError("Prompt 'test_ph' còn chứa placeholder chưa thay thế: ['{var}']"),
        ValueError("Thiếu biến khi render prompt: ['now']"),
    ],
)
def test_format_error_message_maps_prompt_errors_to_user_friendly(exc: Exception):
    """_format_error_message phải map các lỗi cấu hình prompt sang thông báo ngắn gọn tiếng Việt."""
    msg = _format_error_message(exc)
    assert msg == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
    assert "thiếu biến khi render prompt" not in msg.lower()
    assert "now" not in msg
    assert "test_empty" not in msg
    assert len(msg) <= USER_ERROR_MAX_LEN


def test_format_error_message_no_stack_or_template_leak():
    """Thông báo lỗi prompt không được leak traceback hoặc nội dung template."""
    exc = ValueError("Prompt 'agent_system' thiếu biến: ['now']\nTraceback: file.py line 123 SELECT * FROM vehicles")
    msg = _format_error_message(exc)
    assert "traceback" not in msg.lower()
    assert "select" not in msg.lower()
    assert "file.py" not in msg
    assert msg == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."


def test_api_chat_prompt_error_returns_503_friendly_message():
    """Lỗi prompt trong /api/chat trả về HTTP 503 với thông báo tiếng Việt thân thiện."""
    with patch(
        "src.main.run_agent",
        side_effect=ValueError("Prompt 'agent_system' thiếu biến: ['now']"),
    ):
        res = client.post(
            "/api/chat",
            json={
                "question": "Hôm nay có bao nhiêu lượt xe vào?",
                "session_id": "session-test-prompt",
                "user_id": "user-test",
            },
        )
    assert res.status_code == 503
    detail = res.json().get("detail", "")
    assert detail == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
    assert "now" not in detail


def test_api_stream_prompt_error_yields_friendly_answer_sse(monkeypatch):
    """Lỗi prompt trong /api/agent/stream không làm crash generator, trả về __answer__ error."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache

    _cache.clear()

    with patch(
        "src.agent.graph.run_agent_stream",
        side_effect=ValueError("Prompt 'agent_system' thiếu biến: ['now']"),
    ):
        res = client.post(
            "/api/agent/stream",
            json={
                "question": "Hôm nay có bao nhiêu lượt xe vào?",
                "session_id": "session-test-stream",
                "user_id": "user-test",
            },
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
    assert answer.get("output") == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
    assert "traceback" not in str(answer.get("output", "")).lower()


def test_allowed_tables_resource_json_valid():
    """Kiểm tra resource/allowed_tables.json tồn tại và chứa đủ 5 database hợp lệ."""
    import json
    path = Path(__file__).resolve().parent.parent / "resource" / "allowed_tables.json"
    assert path.exists()
    data = json.loads(path.read_text("utf-8"))
    assert "databases" in data
    dbs = data["databases"]
    for expected_db in ["its", "virtual_fence", "smart_face", "firesmoke", "anomaly"]:
        assert expected_db in dbs
        assert len(dbs[expected_db]["allowed_tables"]) > 0


def test_sql_agent_prompt_strict_no_ramble():
    """Kiểm tra prompt sql_agent có quy tắc cấm suy luận lan man và chỉ xuất 1 khối ```sql."""
    from src.prompts import registry
    rendered = registry().render("sql_agent")
    assert "CẤM SUY LUẬN LAN MAN" in rendered or "KHÔNG giải thích" in rendered
    assert "```sql" in rendered


def test_invoke_text_passes_stop_words(monkeypatch):
    """Kiểm tra invoke_text truyền đúng tham số stop vào LLM runnable."""
    from src.llm.client import invoke_text
    from unittest.mock import MagicMock, patch

    mock_llm = MagicMock()
    mock_bound = MagicMock()
    mock_llm.bind.return_value = mock_bound
    mock_bound.invoke.return_value = MagicMock(content="SELECT 1;")

    with patch("src.llm.client.base_llm", return_value=mock_llm):
        out = invoke_text(
            "system prompt",
            "user prompt",
            stop=["```\n\n", "</think>"],
            substep="test_stop",
        )
        mock_llm.bind.assert_called_once_with(stop=["```\n\n", "</think>"])
        assert out == "SELECT 1;"

