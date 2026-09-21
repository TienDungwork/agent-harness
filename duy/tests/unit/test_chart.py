from agent.services.chart_detect import wants_chart
from agent.services.chart_service import render_chart_png


def test_wants_chart_keywords():
    assert wants_chart("Vẽ biểu đồ số lượng xe theo loại")
    assert wants_chart("Thống kê theo ngày")
    assert not wants_chart("Có bao nhiêu camera đang hoạt động?")


def test_render_bar_chart():
    rows = [
        {"vehicle_type": "CAR", "n": 10},
        {"vehicle_type": "MOTORCYCLE", "n": 20},
        {"vehicle_type": "TRUCK", "n": 3},
    ]
    png, meta = render_chart_png(question="biểu đồ theo loại xe", rows=rows)
    assert png
    assert meta.startswith("bar:")
    # PNG magic in base64 starts with iVBOR
    assert png.startswith("iVBOR")
