"""eval/run.py — chạy golden dataset (eval/datasets/agent_stat/*.yaml) qua
ĐÚNG pipeline thật của src/main.py::ask() (guardrail_input → agent →
guardrail_output — cần .env đầy đủ: DB + LLM key), kiểm các assertion khai
báo trong từng case (must_include/must_include_tool/must_not_include/
must_not_include_tool/must_include_columns_any), in tỷ lệ pass/fail theo
slice.type.

Dùng:
    python eval/run.py                                   # dataset mặc định (v2)
    python eval/run.py --dataset eval/datasets/agent_stat/v1.yaml

KHÔNG cần LLM-as-judge (assertion rule-based đủ cho MVP — xem
specs/implementation-plan.md Phase 2). Case nào dùng tool domain mới
(count_face_events/count_fire_smoke_events/count_anomaly_events) sẽ FAIL
cho tới khi Phase 3 + Phase 5 xong (tool chưa tồn tại) — đây là chủ ý, đã
ghi rõ trong header của v2.yaml, không phải lỗi của script này.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.agent.graph import Agent_Input, run_agent
from src.guardrails import GuardrailViolation, OUT_OF_SCOPE_REPLY, check_input, check_output, in_scope, redact_pii

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "agent_stat" / "v2.yaml"


@dataclass
class PipelineResult:
    answer: str
    tools: set[str] = field(default_factory=set)
    columns: list[str] = field(default_factory=list)


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
    evidence = [question] + (
        [f"{c}={v}" for row in query.rows for c, v in zip(query.columns, row)] if query else []
    )
    result = check_output(out.answer, evidence)

    prefix = "tool: "
    tools = {t for t in out.detail[len(prefix) :].split(",") if t} if out.detail.startswith(prefix) else set()
    return PipelineResult(answer=result.answer, tools=tools, columns=query.columns if query else [])


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
            failures.append(f"thiếu must_include_columns_any: cần 1 trong {columns_any}, thật: {sorted(cols) or '(không có)'}")

    return failures


def run(dataset_path: Path) -> int:
    data = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = data["cases"]

    pass_count: Counter[str] = Counter()
    total_count: Counter[str] = Counter()
    fail_details: list[tuple[str, str, list[str]]] = []

    for case in cases:
        slice_type = case["slice"]["type"]
        total_count[slice_type] += 1
        try:
            result = run_pipeline(case["question"])
            failures = check_case(case, result)
        except Exception as exc:  # noqa: BLE001 — muốn thấy lỗi case nào, không dừng cả batch
            failures = [f"lỗi khi chạy pipeline: {type(exc).__name__}: {exc}"]

        if failures:
            fail_details.append((case["id"], case["question"], failures))
        else:
            pass_count[slice_type] += 1

    print(f"Dataset: {data['dataset']} v{data['version']} — {len(cases)} case\n")
    for slice_type in sorted(total_count):
        p, t = pass_count[slice_type], total_count[slice_type]
        print(f"  {slice_type:14s}: {p}/{t} pass")

    total_pass = sum(pass_count.values())
    print(f"\nTổng: {total_pass}/{len(cases)} pass")

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
    args = parser.parse_args()
    sys.exit(run(args.dataset))


if __name__ == "__main__":
    main()
