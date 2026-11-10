from src.infra.monitoring.trace_payload import llm_io_payload, redact_text, slim_state


def test_redact_masks_sk_and_bearer():
    s = redact_text("Bearer SECRETTOKEN123 and sk-abcdef0123456789xyz")
    assert "SECRETTOKEN123" not in s
    assert "sk-abcdef0123456789xyz" not in s
    assert "Bearer" in s or "***" in s


def test_redact_truncates():
    s = redact_text("x" * 100, max_chars=20)
    assert s.endswith("…[truncated]")
    assert len(s) < 40


def test_slim_state_drops_heavy_fields():
    snap = slim_state({
        "question": "q",
        "intent": "query_data",
        "sql": "SELECT 1",
        "error": "",
        "repair_count": 0,
        "rows": [{"a": 1}],
        "events": [{"node_id": "x"}],
        "chart_png_base64": "aaa",
        "messages": [],
        "schema_excerpt": "CREATE TABLE...",
        "orchestrator_step_index": 1,
        "respond_mode": "stat",
        "selected_tables": ["plate_event"],
    })
    assert snap["question"] == "q"
    assert snap["row_count"] == 1
    assert "rows" not in snap
    assert "events" not in snap
    assert "chart_png_base64" not in snap
    assert "schema_excerpt" not in snap


def test_llm_io_payload_has_full_text_not_lens():
    p = llm_io_payload("sys", "usr", "out")
    assert p["input"]["system"] == "sys"
    assert p["input"]["user"] == "usr"
    assert p["output"]["text"] == "out"
    assert "system_len" not in p["input"]


def test_invoke_text_traces_full_prompts(monkeypatch):
    captured: dict = {}

    class _FakeResp:
        content = "hello"
        response_metadata = {}

    class _FakeLlm:
        def invoke(self, _messages):
            return _FakeResp()

    import src.infra.llm.client as client_mod
    import src.infra.monitoring.tracing as tracing_mod

    monkeypatch.setattr(client_mod, "base_llm", lambda **_kw: _FakeLlm())

    from contextlib import contextmanager

    @contextmanager
    def _fake_trace_step(_parent, _name, input=None, metadata=None, as_type="span"):
        box: dict = {"_span": object(), "input": input, "metadata": dict(metadata or {})}
        captured["start_input"] = input
        yield box
        captured["box"] = box

    monkeypatch.setattr(tracing_mod, "trace_step", _fake_trace_step)
    monkeypatch.setattr(tracing_mod, "current_span", lambda: object())
    monkeypatch.setattr(tracing_mod, "extract_token_usage", lambda _r: {})
    monkeypatch.setattr(tracing_mod, "add_request_tokens", lambda _u: None)
    text = client_mod.invoke_text("sys-prompt", "user-prompt", substep="llm_text")
    assert text == "hello"
    assert "system_len" not in captured["start_input"]
    assert captured["start_input"]["system"] == "sys-prompt"
    assert captured["box"]["output"]["text"] == "hello"
