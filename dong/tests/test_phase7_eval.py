"""Unit & Integration tests for Phase 7 — eval/run.py, judge rubric & golden-30 reports."""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from eval.judge import JudgeScore, judge_answer
from eval.run import (
    CaseEvalResult,
    PipelineResult,
    check_case,
    write_golden_30,
    run,
)


def test_judge_answer_offline_skip():
    """Khi môi trường offline/pytest, judge_answer trả về điểm 0 và lý do skipped."""
    score = judge_answer("Câu hỏi test", "Câu trả lời test")
    assert score.score == 0
    assert "skipped" in score.reason.lower()


def test_check_case_rule_validation():
    """Kiểm tra logic check_case cho must_include, must_include_tool, must_not_include, columns_any."""
    case = {
        "id": "test_001",
        "question": "Biển số 15K40139",
        "must_include": ["15K40139", "xe"],
        "must_not_include": ["không tìm thấy"],
        "must_include_tool": ["trace_plate"],
        "must_not_include_tool": ["count_fire_smoke_events"],
        "must_include_columns_any": ["plate", "time_in"],
    }

    # Pass case
    pass_res = PipelineResult(
        answer="Xe biển số 15K40139 xuất hiện lúc 08:00",
        tools={"trace_plate"},
        columns=["plate", "camera_name"],
    )
    assert check_case(case, pass_res) == []

    # Fail must_include
    fail_include = PipelineResult(
        answer="Xe xuất hiện lúc 08:00",
        tools={"trace_plate"},
        columns=["plate"],
    )
    fails = check_case(case, fail_include)
    assert any("thiếu must_include: '15k40139'" in f.lower() for f in fails)

    # Fail must_include_tool
    fail_tool = PipelineResult(
        answer="Xe biển số 15K40139",
        tools={"count_vehicle_flow"},
        columns=["plate"],
    )
    fails = check_case(case, fail_tool)
    assert any("thiếu must_include_tool" in f for f in fails)


def test_write_golden_30_markdown_format(tmp_path: Path):
    """Kiểm tra định dạng file báo cáo markdown golden-30."""
    out_file = tmp_path / "test_golden.md"
    results = [
        CaseEvalResult(
            case_id="case_001",
            slice_type="lookup",
            status="pass",
            latency_ms=120,
            tool="trace_plate",
            note="",
            judge="5/5 — Xuất sắc",
        ),
        CaseEvalResult(
            case_id="case_002",
            slice_type="comparison",
            status="fail",
            latency_ms=80,
            tool="-",
            note="thiếu must_include: '0'",
            judge="2/5 — Thiếu số 0",
        ),
    ]

    path = write_golden_30(
        results,
        dataset="agent_stat",
        version="2.2",
        total_pass=1,
        mode="live",
        output_path=out_file,
    )
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# Golden 30 — eval report" in content
    assert "- dataset: `agent_stat` v2.2" in content
    assert "- mode: live" in content
    assert "- total: 1/2 pass" in content
    assert "| case_001 | lookup | pass | 120 | trace_plate |" in content
    assert "| case_002 | comparison | fail | 80 | - | thiếu must_include: '0' |" in content


def test_eval_run_offline_execution(tmp_path: Path):
    """Kiểm tra eval run với flag offline chạy hoàn tất và ghi báo cáo."""
    dataset_file = Path(__file__).resolve().parent.parent / "eval" / "datasets" / "agent_stat" / "v2.yaml"
    assert dataset_file.exists()

    out_file = tmp_path / "golden_offline.md"
    exit_code = run(dataset_file, output_path=out_file, use_judge=False, offline=True)
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "- mode: offline" in content
    assert "agent_stat_v2_001" in content
