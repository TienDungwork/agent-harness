"""eval/run.py — chạy golden dataset (eval/datasets/agent_stat/*.yaml) qua
ĐÚNG pipeline thật của src/main.py::ask() (guardrail_input → agent →
guardrail_output — cần .env đầy đủ: DB + LLM key), kiểm các assertion khai
báo trong từng case (must_include/must_include_tool/must_not_include/
must_not_include_tool/must_include_columns_any), in tỷ lệ pass/fail theo
slice.type, ghi eval/results/golden-30.md.

Dùng (LIVE — cần .env LLM 196 + DB read-only; không dùng PYTEST_CURRENT_TEST):
    python eval/run.py                                   # dataset mặc định (v2)
    python eval/run.py --judge                           # thêm cột judge 1-5 vào golden-30.md
    python eval/run.py --dataset eval/datasets/agent_stat/v1.yaml

Assertion rule-based đủ cho pass/fail; `--judge` bật LLM chấm nhẹ 1-5 (tuỳ chọn).
Chỉ dùng `--offline` khi mock nhanh (pytest/CI) — không phản ánh chất lượng product.
Case nào dùng tool domain mới
(count_face_events/count_fire_smoke_events/count_anomaly_events) sẽ FAIL
cho tới khi Phase 3 + Phase 5 xong (tool chưa tồn tại) — đây là chủ ý, đã
ghi rõ trong header của v2.yaml, không phải lỗi của script này.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.agent.graph import Agent_Input, run_agent
from eval.judge import judge_answer
from src.guardrails import (
    GuardrailViolation,
    OUT_OF_SCOPE_REPLY,
    _is_tool_empty,
    check_input,
    check_output,
    in_scope,
    redact_pii,
)

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "agent_stat" / "v2.yaml"
GOLDEN_30_PATH = Path(__file__).parent / "results" / "golden-30.md"


def _enable_live_eval() -> None:
    os.environ.pop("PYTEST_CURRENT_TEST", None)
    os.environ["AGENT_EVAL_LIVE"] = "1"


def _disable_live_eval() -> None:
    os.environ.pop("AGENT_EVAL_LIVE", None)


def _preflight_live() -> None:
    from src.config import settings
    from src.llm import ping, use_offline_tools

    if use_offline_tools():
        print("Lỗi: eval product yêu cầu LLM live nhưng đang offline.")
        print(f"  LLM_BACKEND={settings.llm_backend!r}")
        if settings.llm_backend.strip().lower() == "openai" and not settings.api_keys:
            print("  Thiếu OPENAI_API_KEYS — đặt LLM_BACKEND=ollama hoặc self_hosted + LLM_* trong .env")
        sys.exit(1)

    url = settings.llm_base_url or settings.model_base_url or "(default)"
    try:
        ping()
        print(f"LLM ping OK — {url}")
    except Exception as exc:
        print(f"Cảnh báo: LLM ping thất bại ({url}): {exc}")
        print("Tiếp tục eval — case có thể lỗi nếu LLM không phản hồi.")


@dataclass
class PipelineResult:
    answer: str
    tools: set[str] = field(default_factory=set)
    columns: list[str] = field(default_factory=list)
    evidence: str = ""


@dataclass
class CaseEvalResult:
    case_id: str
    slice_type: str
    status: str
    latency_ms: int
    tool: str
    note: str
    judge: str = ""


def run_pipeline(question: str) -> PipelineResult:
    """Lặp lại ĐÚNG pipeline của src/main.py::ask() (guardrail_input → agent
    → guardrail_output) — KHÔNG gọi thẳng run_agent(), vì bỏ qua guardrail
    thì case out_of_scope/injection trong dataset không bao giờ đúng kỳ vọng
    (check_input()/in_scope() mới là nơi sinh ra "prompt_injection_detected"/
    "ngoài phạm vi", run_agent() không biết gì về 2 khái niệm này)."""
    try:
        check_input(question)
    except GuardrailViolation as exc:
        return PipelineResult(answer=exc.reason)

    if not in_scope(question):
        return PipelineResult(answer=OUT_OF_SCOPE_REPLY)

    question = redact_pii(question)
    out = run_agent(Agent_Input(question=question))

    query = out.query
    evidence_parts = [question] + (
        [f"{c}={v}" for row in query.rows for c, v in zip(query.columns, row)] if query else []
    )
    tool_empty = _is_tool_empty(query)
    result = check_output(out.answer, evidence_parts, tool_empty=tool_empty)

    prefix = "tool: "
    tools = {t for t in out.detail[len(prefix) :].split(",") if t} if out.detail.startswith(prefix) else set()
    return PipelineResult(
        answer=result.answer,
        tools=tools,
        columns=query.columns if query else [],
        evidence=" | ".join(evidence_parts),
    )


def _evidence_text(result: PipelineResult) -> str:
    return f"{result.answer} {' '.join(result.tools)}".lower()


def check_case(case: dict, result: PipelineResult) -> list[str]:
    """Trả về list lý do fail — rỗng nghĩa là pass."""
    failures: list[str] = []
    text = _evidence_text(result)
    tools = result.tools

    for needle in case.get("must_include", []):
        if needle.lower() not in text:
            failures.append(f"thiếu must_include: '{needle}'")

    for needle in case.get("must_not_include", []):
        if needle.lower() in text:
            failures.append(f"có must_not_include (không được có): '{needle}'")

    for tool in case.get("must_include_tool", []):
        if tool not in tools:
            failures.append(f"thiếu must_include_tool: '{tool}' (tool thật: {sorted(tools) or '(không có)'})")

    for tool in case.get("must_not_include_tool", []):
        if tool in tools:
            failures.append(f"gọi nhầm must_not_include_tool: '{tool}'")

    columns_any = case.get("must_include_columns_any")
    if columns_any:
        cols = set(result.columns)
        if not any(c in cols for c in columns_any):
            failures.append(
                f"thiếu must_include_columns_any: cần 1 trong {columns_any}, thật: {sorted(cols) or '(không có)'}"
            )

    return failures


def _format_tool(tools: set[str]) -> str:
    return ",".join(sorted(tools)) if tools else "-"


def _escape_md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def write_golden_30(
    results: list[CaseEvalResult],
    *,
    dataset: str,
    version: str,
    total_pass: int,
    mode: str = "live",
    output_path: Path | None = None,
) -> Path:
    """Ghi báo cáo markdown golden-30 — một dòng mỗi case."""
    path = output_path or GOLDEN_30_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Golden 30 — eval report",
        "",
        f"- dataset: `{dataset}` v{version}",
        f"- mode: {mode}",
        f"- generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"- total: {total_pass}/{len(results)} pass",
        "",
        "| id | slice | pass/fail | latency_ms | tool | note | judge |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in results:
        lines.append(
            f"| {row.case_id} | {row.slice_type} | {row.status} | {row.latency_ms} | "
            f"{_escape_md_cell(row.tool)} | {_escape_md_cell(row.note)} | {_escape_md_cell(row.judge)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(
    dataset_path: Path,
    *,
    output_path: Path | None = None,
    use_judge: bool = False,
    offline: bool = False,
) -> int:
    if offline:
        _disable_live_eval()
    else:
        _enable_live_eval()
        _preflight_live()

    data = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = data["cases"]

    pass_count: Counter[str] = Counter()
    total_count: Counter[str] = Counter()
    fail_details: list[tuple[str, str, list[str]]] = []
    golden_rows: list[CaseEvalResult] = []

    for case in cases:
        slice_type = case["slice"]["type"]
        total_count[slice_type] += 1
        t0 = time.perf_counter()
        pipeline_result: PipelineResult | None = None
        try:
            pipeline_result = run_pipeline(case["question"])
            failures = check_case(case, pipeline_result)
        except Exception as exc:  # noqa: BLE001 — muốn thấy lỗi case nào, không dừng cả batch
            failures = [f"lỗi khi chạy pipeline: {type(exc).__name__}: {exc}"]

        latency_ms = int((time.perf_counter() - t0) * 1000)
        tools = pipeline_result.tools if pipeline_result else set()
        
        judge_str = ""
        if use_judge and pipeline_result:
            score_res = judge_answer(
                question=case["question"],
                answer=pipeline_result.answer,
                evidence=pipeline_result.evidence,
                expected=case.get("expected", ""),
            )
            judge_str = f"{score_res.score}/5 — {score_res.reason}" if score_res.score else score_res.reason

        golden_rows.append(
            CaseEvalResult(
                case_id=case["id"],
                slice_type=slice_type,
                status="fail" if failures else "pass",
                latency_ms=latency_ms,
                tool=_format_tool(tools),
                note="; ".join(failures),
                judge=judge_str,
            )
        )

        if failures:
            fail_details.append((case["id"], case["question"], failures))
        else:
            pass_count[slice_type] += 1

    total_pass = sum(pass_count.values())
    report_path = write_golden_30(
        golden_rows,
        dataset=data.get("dataset", dataset_path.stem),
        version=str(data.get("version", "")),
        total_pass=total_pass,
        mode="offline" if offline else "live",
        output_path=output_path,
    )

    print(f"Dataset: {data['dataset']} v{data['version']} — {len(cases)} case\n")
    for slice_type in sorted(total_count):
        p, t = pass_count[slice_type], total_count[slice_type]
        print(f"  {slice_type:14s}: {p}/{t} pass")

    print(f"\nTổng: {total_pass}/{len(cases)} pass")
    print(f"\nĐã ghi: {report_path}")

    if fail_details:
        print("\nChi tiết case FAIL:")
        for case_id, question, failures in fail_details:
            print(f"  [{case_id}] {question}")
            for reason in failures:
                print(f"      - {reason}")

    return 0 if not fail_details else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=GOLDEN_30_PATH, help="Đường dẫn golden-30.md")
    parser.add_argument("--judge", action="store_true", help="Chạy judge bằng LLM cho từng case")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Mock offline (pytest/CI) — KHÔNG dùng cho đánh giá product thật",
    )
    args = parser.parse_args()
    sys.exit(run(args.dataset, output_path=args.output, use_judge=args.judge, offline=args.offline))


if __name__ == "__main__":
    main()
