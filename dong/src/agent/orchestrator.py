"""Multi-agent Orchestrator MVP (dong v5).

Điều phối phân rã câu hỏi phức tạp thành 1–2 bước chuyên gia (query_data | docs)
và tổng hợp kết quả (không swarm).
Hỗ trợ offline heuristics phục vụ pytest và fallback, cùng online LLM call qua prompt registry.
"""

from __future__ import annotations

from typing import Literal

from src.llm.client import use_offline_tools
from src.llm.schemas import OrchestratorPlan, OrchestratorStep
from src.llm.structured import invoke_structured
from src.prompts import registry

STAT_KEYWORDS = (
    "hôm nay có",
    "bao nhiêu",
    "phát hiện",
    "cảnh báo",
    "leo trèo",
    "cháy",
    "khói",
    "mực nước",
    "đám đông",
    "ẩu đả",
    "vụ ẩu đả",
    "lượt xe",
    "ra vào",
    "biểu đồ",
    "thống kê",
    "xâm nhập",
    "số lượng",
    "số lượt",
    "vào cổng",
    "ra cổng",
)

DOCS_KEYWORDS = (
    "aioc",
    "devices",
    "quản lý camera",
    "thêm camera",
    "trực tuyến",
    "ngoại tuyến",
    "bảo trì",
    "vẽ sơ đồ",
    "sơ đồ",
    "hướng dẫn",
    "làm sao",
    "đăng nhập",
    "đăng xuất",
    "cách mở",
    "cách dùng",
    "cài đặt",
    "sử dụng",
    "xem lại",
)

SPLIT_PATTERNS = (
    ", rồi cho biết ",
    " rồi cho biết ",
    ", rồi ",
    " rồi ",
    ", và cho biết ",
    " và cho biết ",
    ", khác gì so với ",
    " khác gì so với ",
)


def is_multi_question(question: str) -> bool:
    """Kiểm tra heuristic xem câu hỏi có chứa mẫu tách multi-agent không."""
    low = (question or "").lower().strip()
    return any(pat in low for pat in SPLIT_PATTERNS)


def _classify_sub_question(text: str) -> Literal["query_data", "docs"]:
    """Phân loại 1 sub-question sang query_data hoặc docs dựa trên từ khóa."""
    low = text.lower().strip()
    # Nếu là câu hỏi phân biệt/so sánh cách dùng/khái niệm với câu hỏi thống kê (vd: case 024)
    if ("khác gì so với" in low or "phân biệt" in low) and any(d in low for d in DOCS_KEYWORDS):
        return "docs"

    has_stat = any(k in low for k in STAT_KEYWORDS)
    has_docs = any(k in low for k in DOCS_KEYWORDS)

    # Nếu có từ khóa thống kê cụ thể (leo trèo, cháy, khói, mực nước, đám đông, bao nhiêu, hôm nay có cảnh báo/phát hiện)
    if has_stat:
        # Nếu thuần túy là howto mở trang / sơ đồ mà không chứa từ khóa sự kiện thực tế
        if not any(k in low for k in ("leo trèo", "cháy", "khói", "mực nước", "đám đông", "ẩu đả", "bao nhiêu", "lượt xe", "cảnh báo")):
            if has_docs:
                return "docs"
        return "query_data"

    if has_docs:
        return "docs"

    return "query_data"


def _offline_plan_orchestration(question: str) -> OrchestratorPlan:
    """Heuristic offline cho orchestrator khi chạy pytest hoặc LLM offline."""
    text = (question or "").strip()
    low = text.lower()

    # 1. Out of scope check
    if any(k in low for k in ("thời tiết", "bóng đá", "tổng thống", "chính trị", "giá vàng", "nấu ăn", "bài thơ", "cổ phiếu")):
        return OrchestratorPlan(
            steps=[],
            is_multi=False,
            reason="Offline heuristic: câu hỏi ngoài phạm vi",
        )

    # 2. Case so sánh sơ đồ / howto AIOC với câu hỏi thống kê (case 024):
    # Cần docs cho phần sơ đồ/hướng dẫn, không điều hướng cả câu hỏi sang SQL
    if ("vẽ sơ đồ" in low or "sơ đồ" in low) and ("khác gì so với" in low or "phân biệt" in low):
        return OrchestratorPlan(
            steps=[OrchestratorStep(agent="docs", sub_question=text)],
            is_multi=False,
            reason="Offline heuristic: docs-focused sơ đồ và phân biệt khái niệm (không gọi SQL)",
        )

    # 3. Thử tách 2 bước dựa trên các mẫu nối câu: "rồi", "và cho biết", "khác gì so với"
    for pat in SPLIT_PATTERNS:
        if pat in low:
            idx = low.find(pat)
            part1 = text[:idx].strip().rstrip(",")
            part2 = text[idx + len(pat):].strip()
            if part1 and part2:
                agent1 = _classify_sub_question(part1)
                agent2 = _classify_sub_question(part2)

                # Trường hợp multi-agent kết hợp docs và query_data (vd: case 023)
                if agent1 != agent2:
                    return OrchestratorPlan(
                        steps=[
                            OrchestratorStep(agent=agent1, sub_question=part1),
                            OrchestratorStep(agent=agent2, sub_question=part2),
                        ],
                        is_multi=True,
                        reason=f"Offline heuristic: 2 bước multi-agent ({agent1} + {agent2})",
                    )
                # Nếu cả 2 phần đều là docs
                elif agent1 == "docs":
                    return OrchestratorPlan(
                        steps=[OrchestratorStep(agent="docs", sub_question=text)],
                        is_multi=False,
                        reason="Offline heuristic: câu hỏi docs chuyên biệt",
                    )

    # 4. Phân loại 1 bước đơn (Single step)
    agent = _classify_sub_question(text)
    return OrchestratorPlan(
        steps=[OrchestratorStep(agent=agent, sub_question=text)],
        is_multi=False,
        reason=f"Offline heuristic: single-step agent={agent}",
    )


def plan_orchestration(question: str) -> OrchestratorPlan:
    """Lập kế hoạch điều phối 1–2 bước chuyên gia (query_data | docs)."""
    clean_q = (question or "").strip()
    if not clean_q:
        return OrchestratorPlan(steps=[], is_multi=False, reason="Câu hỏi rỗng")

    if use_offline_tools():
        return _offline_plan_orchestration(clean_q)

    try:
        messages = [
            {"role": "system", "content": registry().render("orchestrator")},
            {"role": "user", "content": f"Câu hỏi của người dùng:\n{clean_q}"},
        ]
        return invoke_structured(messages, OrchestratorPlan)
    except Exception:
        return _offline_plan_orchestration(clean_q)
