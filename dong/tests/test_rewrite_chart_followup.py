"""Rewrite kế thừa yêu cầu vẽ biểu đồ ở câu follow-up."""

from unittest.mock import MagicMock, patch

from src.domain.agents.vms.nodes.rewrite import (
    _apply_chart_followup_inheritance,
    rewrite_question,
)
from src.infra.chart.render import should_render_chart
from src.infra.llm.schemas import RewrittenQuestion


def test_apply_chart_followup_injects_vẽ_when_history_had_chart():
    history = [{"role": "user", "content": "vẽ biểu đồ xe ra vào hôm nay?"}]
    raw = RewrittenQuestion(
        text="Thống kê số lượng sự kiện xâm nhập vùng cấm hôm nay",
        sub_questions=["Hôm nay có bao nhiêu sự kiện xâm nhập vùng cấm?"],
    )
    out = _apply_chart_followup_inheritance("Vậy còn vùng cấm thì sao?", history, raw)
    assert should_render_chart(out.text)
    assert all(should_render_chart(s) for s in out.sub_questions)


def test_apply_chart_followup_skips_when_prior_turn_no_chart():
    history = [{"role": "user", "content": "Hôm nay có bao nhiêu xe vào?"}]
    raw = RewrittenQuestion(
        text="Thống kê sự kiện vùng cấm hôm nay",
        sub_questions=["Hôm nay có bao nhiêu sự kiện vùng cấm?"],
    )
    out = _apply_chart_followup_inheritance("Vậy còn vùng cấm?", history, raw)
    assert out.text == raw.text


@patch("src.domain.agents.vms.nodes.rewrite.invoke_structured")
def test_rewrite_question_post_process_after_llm(mock_invoke):
    mock_invoke.return_value = RewrittenQuestion(
        text="Thống kê số lượng sự kiện xâm nhập vùng cấm hôm nay",
        sub_questions=["Hôm nay có bao nhiêu sự kiện xâm nhập vùng cấm?"],
    )
    history = [{"role": "user", "content": "vẽ biểu đồ xe ra vào hôm nay?"}]
    out = rewrite_question("Vậy còn vùng cấm thì sao?", history=history)
    assert should_render_chart(out.text)
    mock_invoke.assert_called_once()
