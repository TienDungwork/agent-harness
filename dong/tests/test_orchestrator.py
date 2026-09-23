"""Unit tests for Multi-agent Orchestrator MVP (Phase 3c).

Kiểm tra:
- plan_orchestration định tuyến các case fail golden:
  * 009/010/011 -> query_data
  * 015/017 -> docs
  * 023 -> 2 steps (docs + query_data)
  * 024 -> docs-focused (không chuyển toàn bộ câu hỏi sang SQL)
- offline graph/run_agent cho case 009 đi qua nhánh SQL (query_data), không phải docs
- query_plan offline cho đám đông (case 008) sinh filter CROWD_DETECTION
- case 008 trả về kết quả có số '0'
- case 015 chứa 'trực tuyến'
- case 017 chứa 'camera'
- case 023 chạy multi-agent trả về đầy đủ 'aioc.atin.vn' và tool 'sql_builder'
- case 024 trả về 'devices' và không gọi 'sql_builder'
- trace events của graph ghi nhận đầy đủ node orchestrator
"""

from unittest.mock import patch

from src.agent.graph import Agent_Input, _build_graph, run_agent, run_agent_stream
from src.agent.generate_sql import generate_sql_node
from src.agent.orchestrator import plan_orchestration
from src.db.catalog import select_relevant_tables
from src.llm.schemas import OrchestratorPlan, OrchestratorStep


def test_plan_orchestration_routes_009_010_011_to_query_data():
    """Case 009 (leo trèo), 010 (cháy khói), 011 (mực nước) định tuyến sang query_data."""
    # 009: "Hôm nay có phát hiện leo trèo không?"
    q_009 = "Hôm nay có phát hiện leo trèo không?"
    plan_009 = plan_orchestration(q_009)
    assert isinstance(plan_009, OrchestratorPlan)
    assert len(plan_009.steps) >= 1
    assert plan_009.steps[0].agent == "query_data"

    # 010: "Hôm nay có cảnh báo cháy hoặc khói không?"
    q_010 = "Hôm nay có cảnh báo cháy hoặc khói không?"
    plan_010 = plan_orchestration(q_010)
    assert len(plan_010.steps) >= 1
    assert plan_010.steps[0].agent == "query_data"

    # 011: "Hôm nay mực nước có vượt ngưỡng cảnh báo không?"
    q_011 = "Hôm nay mực nước có vượt ngưỡng cảnh báo không?"
    plan_011 = plan_orchestration(q_011)
    assert len(plan_011.steps) >= 1
    assert plan_011.steps[0].agent == "query_data"


def test_plan_orchestration_routes_015_017_to_docs():
    """Case 015 (trạng thái trực tuyến AIOC) và 017 (sơ đồ thêm camera AIOC) định tuyến sang docs."""
    # 015: "Trên AIOC devices, trạng thái camera Trực Tuyến / Ngoại Tuyến / Bảo Trì nghĩa là gì và đổi ở đâu?"
    q_015 = "Trên AIOC devices, trạng thái camera Trực Tuyến / Ngoại Tuyến / Bảo Trì nghĩa là gì và đổi ở đâu?"
    plan_015 = plan_orchestration(q_015)
    assert isinstance(plan_015, OrchestratorPlan)
    assert len(plan_015.steps) >= 1
    assert plan_015.steps[0].agent == "docs"

    # 017: "Vẽ sơ đồ quy trình thêm một camera mới trên AIOC (từ mở form đến tạo xong)."
    q_017 = "Vẽ sơ đồ quy trình thêm một camera mới trên AIOC (từ mở form đến tạo xong)."
    plan_017 = plan_orchestration(q_017)
    assert len(plan_017.steps) >= 1
    assert plan_017.steps[0].agent == "docs"


def test_plan_orchestration_case_023_two_steps_docs_and_query():
    """Case 023 kết hợp howto devices + thống kê cháy/khói -> 2 steps (docs + query_data)."""
    q_023 = (
        "Chỉ tôi cách mở Quản Lý Camera trên AIOC (https://aioc.atin.vn/devices), "
        "rồi cho biết hôm nay có cảnh báo cháy hoặc khói không?"
    )
    plan_023 = plan_orchestration(q_023)
    assert plan_023.is_multi is True
    assert len(plan_023.steps) == 2

    agents = [s.agent for s in plan_023.steps]
    assert agents[0] == "docs"
    assert agents[1] == "query_data"
    assert "aioc" in plan_023.steps[0].sub_question.lower() or "devices" in plan_023.steps[0].sub_question.lower()
    assert "cháy" in plan_023.steps[1].sub_question.lower() or "khói" in plan_023.steps[1].sub_question.lower()


def test_plan_orchestration_case_024_docs_focused_not_sql_only():
    """Case 024 so sánh sơ đồ thêm camera với câu hỏi thống kê -> docs-focused, không route cả câu sang SQL."""
    q_024 = (
        "Vẽ sơ đồ các bước thêm camera trên AIOC devices, "
        "và cho biết khác gì so với câu hỏi thống kê số lượt xe hôm nay?"
    )
    plan_024 = plan_orchestration(q_024)
    # Docs-focused: bước đầu tiên phải là docs
    assert plan_024.steps[0].agent == "docs"
    # Không được route cả câu hỏi chỉ sang SQL
    assert not all(s.agent == "query_data" for s in plan_024.steps)
    assert all(s.agent != "query_data" for s in plan_024.steps)


def test_query_plan_offline_crowd_filter_crowd_detection():
    """Case 008: query offline với đám đông phải có filter event_type=CROWD_DETECTION."""
    q_008 = "Trong khoảng từ 04/09/2026 đến 16/09/2026 có bao nhiêu lượt phát hiện đám đông?"
    tables = select_relevant_tables(q_008)
    assert tables == ["anomaly_event"]
    res = generate_sql_node({"question": q_008})
    assert "anomaly_event" in res["sql"]
    assert "CROWD_DETECTION" in res["sql"]


def test_query_plan_offline_anomaly_filters():
    """Kiểm tra các filter anomaly khác: leo trèo, mực nước, ẩu đả."""
    res_intrusion = generate_sql_node({"question": "Hôm nay có phát hiện leo trèo không?"})
    assert "anomaly_event" in res_intrusion["sql"]
    assert "INTRUSION_DETECTION" in res_intrusion["sql"]

    res_water = generate_sql_node({"question": "Hôm nay mực nước có vượt ngưỡng cảnh báo không?"})
    assert "anomaly_event" in res_water["sql"]
    assert "WATER_LEVEL_DETECTION" in res_water["sql"]

    res_fight = generate_sql_node({"question": "Trong khoảng này có bao nhiêu vụ ẩu đả?"})
    assert "anomaly_event" in res_fight["sql"]
    assert "FIGHT_DETECTION" in res_fight["sql"]


def test_offline_graph_run_agent_case_009_hits_sql_path_not_docs():
    """Chạy run_agent offline cho case 009 đi vào nhánh SQL (query_data), không phải docs."""
    inp = Agent_Input(question="Hôm nay có phát hiện leo trèo không?")
    res = run_agent(inp)
    assert res.detail == "query_data"
    assert res.detail != "docs"
    assert res.query is not None
    assert res.query.tool == "sql_builder"


def test_offline_graph_run_agent_case_008_includes_zero():
    """Case 008: kết quả đếm đám đông phải trả về số 0 khi không có sự kiện."""
    inp = Agent_Input(question="Trong khoảng từ 04/09/2026 đến 16/09/2026 có bao nhiêu lượt phát hiện đám đông?")
    res = run_agent(inp)
    assert "0" in res.answer


def test_offline_graph_run_agent_case_015_includes_truc_tuyen():
    """Case 015: câu trả lời tài liệu AIOC phải chứa 'trực tuyến'."""
    q = "Trên AIOC devices, trạng thái camera Trực Tuyến / Ngoại Tuyến / Bảo Trì nghĩa là gì và đổi ở đâu?"
    res = run_agent(Agent_Input(question=q))
    assert res.detail == "docs"
    assert "trực tuyến" in res.answer.lower()


def test_offline_graph_run_agent_case_017_includes_camera():
    """Case 017: sơ đồ thêm camera AIOC phải chứa 'camera'."""
    q = "Vẽ sơ đồ quy trình thêm một camera mới trên AIOC (từ mở form đến tạo xong)."
    res = run_agent(Agent_Input(question=q))
    assert res.detail == "docs"
    assert "camera" in res.answer.lower()


def test_offline_graph_run_agent_case_023_multi_agent():
    """Case 023: chạy qua orchestrator multi kết hợp cả docs ('aioc.atin.vn') và tool 'sql_builder'."""
    q = (
        "Chỉ tôi cách mở Quản Lý Camera trên AIOC (https://aioc.atin.vn/devices), "
        "rồi cho biết hôm nay có cảnh báo cháy hoặc khói không?"
    )
    res = run_agent(Agent_Input(question=q))
    assert "aioc.atin.vn" in res.answer
    assert res.query is not None
    assert res.query.tool == "sql_builder"


def test_offline_graph_run_agent_case_024_docs_no_sql():
    """Case 024: trả lời có 'devices' và không gọi tool sql_builder."""
    q = (
        "Vẽ sơ đồ các bước thêm camera trên AIOC devices, "
        "và cho biết khác gì so với câu hỏi thống kê số lượt xe hôm nay?"
    )
    res = run_agent(Agent_Input(question=q))
    assert res.detail == "docs"
    assert "devices" in res.answer.lower()
    assert res.query is None


def test_graph_emits_orchestrator_events_in_stream():
    """Stream event chứa node_id 'orchestrator' với input và output đầy đủ."""
    inp = Agent_Input(question="Hướng dẫn mở quản lý camera, và cho biết hôm nay có bao nhiêu lượt xe?")
    events = list(run_agent_stream(inp))
    done_orchestrator = [ev for ev in events if ev.get("node_id") == "orchestrator" and ev.get("status") == "done"]
    assert len(done_orchestrator) == 1
    assert done_orchestrator[0].get("input")
    assert done_orchestrator[0].get("output")
    out = done_orchestrator[0]["output"]
    plan = out.get("orchestrator_plan") if isinstance(out, dict) else {}
    agents = [s.get("agent") for s in (plan.get("steps") or [])]
    assert "query_data" in agents


@patch("src.agent.orchestrator.use_offline_tools", return_value=False)
@patch("src.agent.orchestrator.invoke_structured")
def test_plan_orchestration_mock_online(mock_invoke, _mock_offline):
    """Kiểm tra online orchestrator gọi invoke_structured qua prompt registry."""
    expected = OrchestratorPlan(
        steps=[
            OrchestratorStep(agent="docs", sub_question="cách mở Quản Lý Camera"),
            OrchestratorStep(agent="query_data", sub_question="thống kê cháy nổ"),
        ],
        is_multi=True,
        reason="Câu hỏi kết hợp docs và data",
    )
    mock_invoke.return_value = expected
    plan = plan_orchestration("câu hỏi kết hợp")
    assert plan == expected
    assert mock_invoke.called
