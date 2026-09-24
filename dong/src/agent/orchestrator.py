"""Multi-agent Orchestrator MVP (dong v5).

Điều phối phân rã câu hỏi phức tạp thành 1–2 bước chuyên gia (query_data | docs)
và tổng hợp kết quả (không swarm).
Hỗ trợ offline heuristics phục vụ pytest và fallback, cùng online LLM call qua prompt registry.
"""

from __future__ import annotations

import re
from typing import Literal

from src.db.catalog import get_database_for_table
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
    "vi phạm",
    "gần nhất",
    "mới nhất",
    "gần đây nhất",
    "lúc nào",
    "phương tiện",
    "ô tô",
    "xe máy",
    "xe tải",
    "biển số",
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
    ", và cho tôi biết ",
    " và cho tôi biết ",
    ", cho tôi biết ",
    ", cho biết ",
    ", khác gì so với ",
    " khác gì so với ",
    ", và đồng thời ",
    " và đồng thời ",
    ", đồng thời ",
    " đồng thời ",
    ", và ",
    "? và ",
)

_COMPARISON_MARKERS = (
    "nhiều hơn",
    "nhieu hon",
    "ít hơn",
    "it hon",
    "cao hơn",
    "cao hon",
    "thấp hơn",
    "thap hon",
    "so sánh",
    "so sanh",
)

_DOMAIN_PHRASES: list[tuple[tuple[str, ...], str]] = [
    (("phương tiện", "phuong tien", "lượt xe", "luot xe", "biển số", "bien so", "xe máy", "xe may", "ô tô", "o to"), "plate_event"),
    (("vùng cấm", "vung cam", "xâm nhập", "xam nhap", "hàng rào", "hang rao", "leo trèo", "leo treo"), "zone_event"),
    (("cháy", "chay", "khói", "khoi", "hỏa hoạn", "hoa hoan"), "fire_smoke_event"),
    (("khuôn mặt", "khuon mat", "gương mặt", "guong mat", "nhận diện mặt"), "smf_face_events"),
    (("ẩu đả", "au da", "đám đông", "dam dong", "đánh nhau", "danh nhau", "mực nước", "muc nuoc", "ngập", "ngap"), "anomaly_event"),
]

_HAY_SUFFIX = re.compile(
    r"\s*(?:xảy ra\s+)?(?:nhiều hơn|nhieu hon|ít hơn|it hon|cao hơn|cao hon|thấp hơn|thap hon|so sánh|so sanh).*$",
    re.IGNORECASE,
)

_ALL_EVENTS_RE = re.compile(
    r"tất\s*c(?:ả|à)\s*(?:các\s*)?(?:event|events|sự\s*kiện|su\s*kien)|"
    r"(?:toàn\s*bộ|mọi)\s*(?:các\s*)?(?:event|events|sự\s*kiện|su\s*kien)",
    re.IGNORECASE,
)

_ALL_EVENT_DOMAIN_LABELS: list[str] = [
    "phương tiện",
    "vùng cấm",
    "khuôn mặt",
    "cháy/khói",
    "bất thường",
]

ALL_EVENTS_PLAN_REASON = "all_events_aggregate"
REWRITE_SUBQUESTIONS_PLAN_REASON = "rewrite_sub_questions"


def _is_howto_diagram_only(question: str) -> bool:
    """Sơ đồ hướng dẫn AIOC/howto — không phải biểu đồ thống kê dữ liệu."""
    low = (question or "").lower()
    if not any(k in low for k in ("vẽ sơ đồ", "sơ đồ", "flowchart", "quy trình")):
        return False
    if any(k in low for k in ("aioc", "devices", "đăng nhập", "thêm camera", "phân biệt", "khác gì")):
        return True
    if _ALL_EVENTS_RE.search(low) or any(k in low for k in ("số lượng", "thống kê", "bao nhiêu")):
        return False
    return True


def is_all_events_aggregate(question: str) -> bool:
    """True khi hỏi tổng hợp số lượng mọi loại sự kiện VMS (cross-DB)."""
    low = (question or "").lower()
    if not _ALL_EVENTS_RE.search(low):
        return False
    if _is_howto_diagram_only(question):
        return False
    return any(
        k in low
        for k in (
            "số lượng",
            "so luong",
            "thống kê",
            "thong ke",
            "biểu đồ",
            "bieu do",
            "chart",
            "vẽ sơ đồ",
            "ve so do",
            "bao nhiêu",
            "bao nhieu",
            "đếm",
            "dem",
        )
    )


def is_all_events_plan(plan: OrchestratorPlan | None) -> bool:
    return bool(plan and getattr(plan, "reason", "") == ALL_EVENTS_PLAN_REASON)


def _time_lead_from_question(question: str) -> str:
    low = (question or "").lower()
    if "hôm nay" in low or "hom nay" in low:
        return "Hôm nay"
    if "hôm qua" in low or "hom qua" in low:
        return "Hôm qua"
    if "tháng này" in low or "thang nay" in low:
        return "Tháng này"
    m = re.search(r"từ\s*(\d{1,2}/\d{1,2}/\d{4})\s*đến\s*(\d{1,2}/\d{1,2}/\d{4})", question or "", re.I)
    if m:
        return f"Trong khoảng từ {m.group(1)} đến {m.group(2)}"
    return "Trong khoảng thời gian đã cho"


def _plan_all_events_aggregate(question: str) -> OrchestratorPlan:
    """Phân rã 'tất cả event' thành N bước query_data — mỗi domain một DB."""
    lead = _time_lead_from_question(question)
    steps = [
        OrchestratorStep(
            agent="query_data",
            sub_question=f"{lead}, có bao nhiêu sự kiện {label}?".strip().strip(","),
        )
        for label in _ALL_EVENT_DOMAIN_LABELS
    ]
    return OrchestratorPlan(
        steps=steps,
        is_multi=True,
        reason=ALL_EVENTS_PLAN_REASON,
    )


def _table_for_phrase(text: str) -> str | None:
    low = (text or "").lower()
    for phrases, tbl in _DOMAIN_PHRASES:
        if any(p in low for p in phrases):
            return tbl
    return None


def _split_hay_comparison(question: str) -> tuple[str, str, str] | None:
    """Tách câu dạng '…, A hay B … nhiều hơn?' thành (prefix, A, B)."""
    low = (question or "").lower()
    if " hay " not in low or not any(m in low for m in _COMPARISON_MARKERS):
        return None
    idx = low.find(" hay ")
    left_text = question[:idx].strip().rstrip(",").rstrip("?")
    right_rest = _HAY_SUFFIX.sub("", question[idx + 5 :]).strip().rstrip("?")
    if not right_rest:
        return None
    if "," in left_text:
        prefix, left_part = left_text.rsplit(",", 1)
        prefix = prefix.strip() + ","
    else:
        prefix, left_part = "", left_text
    left_part = left_part.strip()
    if not left_part or not right_rest:
        return None
    return prefix, left_part, right_rest


def is_cross_domain_comparison(question: str) -> bool:
    """True khi 'A hay B' so sánh hai domain thuộc database khác nhau."""
    parts = _split_hay_comparison(question)
    if not parts:
        return False
    _, left, right = parts
    t_left, t_right = _table_for_phrase(left), _table_for_phrase(right)
    if not t_left or not t_right or t_left == t_right:
        return False
    return get_database_for_table(t_left) != get_database_for_table(t_right)


def _plan_cross_domain_comparison(question: str) -> OrchestratorPlan | None:
    """Phân rã so sánh cross-database thành 2 bước query_data độc lập."""
    parts = _split_hay_comparison(question)
    if not parts:
        return None
    prefix, left, right = parts
    t_left, t_right = _table_for_phrase(left), _table_for_phrase(right)
    if not t_left or not t_right or t_left == t_right:
        return None
    if get_database_for_table(t_left) == get_database_for_table(t_right):
        return None
    lead = f"{prefix} " if prefix else ""
    return OrchestratorPlan(
        steps=[
            OrchestratorStep(agent="query_data", sub_question=f"{lead}có bao nhiêu sự kiện {left}?".strip()),
            OrchestratorStep(agent="query_data", sub_question=f"{lead}có bao nhiêu sự kiện {right}?".strip()),
        ],
        is_multi=True,
        reason=f"So sánh cross-database ({t_left} vs {t_right}) — tách 2 truy vấn đơn",
    )


def _multi_question_heuristics(*questions: str) -> bool:
    for q in questions:
        if not (q or "").strip():
            continue
        low = q.lower().strip()
        if is_all_events_aggregate(q):
            return True
        if any(pat in low for pat in SPLIT_PATTERNS):
            return True
        if is_cross_domain_comparison(q):
            return True
    return False


def is_multi_question(
    question: str,
    rewritten: object | None = None,
    original: str = "",
    intent: str = "",
) -> bool:
    """Kiểm tra heuristic xem câu hỏi có chứa mẫu tách multi-agent không."""
    if _multi_question_heuristics(question, original):
        return True
    if intent in ("how_to", "troubleshoot", "concept", "chat", "clarify"):
        return False
    if intent in ("query_data", "out_of_scope", "") and is_rewrite_multi(rewritten, original):
        return True
    return False


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

    # 3. Thử tách 2 bước dựa trên các mẫu nối câu: "rồi", "và cho biết", ", và ", "khác gì so với"
    for pat in SPLIT_PATTERNS:
        if pat in low:
            idx = low.find(pat)
            part1 = text[:idx].strip().rstrip(",").rstrip("?")
            part2 = text[idx + len(pat):].strip()
            if part1 and part2:
                agent1 = _classify_sub_question(part1)
                agent2 = _classify_sub_question(part2)

                # Nếu cả 2 phần đều là docs
                if agent1 == "docs" and agent2 == "docs":
                    return OrchestratorPlan(
                        steps=[OrchestratorStep(agent="docs", sub_question=text)],
                        is_multi=False,
                        reason="Offline heuristic: câu hỏi docs chuyên biệt",
                    )
                else:
                    return OrchestratorPlan(
                        steps=[
                            OrchestratorStep(agent=agent1, sub_question=part1),
                            OrchestratorStep(agent=agent2, sub_question=part2),
                        ],
                        is_multi=True,
                        reason=f"Offline heuristic: 2 bước multi-agent ({agent1} + {agent2})",
                    )

    # 4. Phân loại 1 bước đơn (Single step)
    agent = _classify_sub_question(text)
    return OrchestratorPlan(
        steps=[OrchestratorStep(agent=agent, sub_question=text)],
        is_multi=False,
        reason=f"Offline heuristic: single-step agent={agent}",
    )


def _plan_diagram_concept_docs(question: str) -> OrchestratorPlan | None:
    """Sơ đồ/phân biệt khái niệm AIOC — docs only, không SQL."""
    low = (question or "").lower()
    if ("vẽ sơ đồ" in low or "sơ đồ" in low) and ("khác gì so với" in low or "phân biệt" in low):
        return OrchestratorPlan(
            steps=[OrchestratorStep(agent="docs", sub_question=question.strip())],
            is_multi=False,
            reason="Sơ đồ và phân biệt khái niệm — docs only",
        )
    return None


def plan_from_rewrite_sub_questions(
    sub_questions: list[str],
    original: str = "",
) -> OrchestratorPlan | None:
    """Dùng sub_questions từ rewrite khi có ≥2 ý độc lập — mỗi ý một bước orchestrator."""
    subs = [s.strip() for s in (sub_questions or []) if (s or "").strip()]
    if len(subs) < 2:
        return None
    if not _multi_question_heuristics(original, *subs) and not _subs_are_cross_domain(subs):
        return None
    steps = [OrchestratorStep(agent=_classify_sub_question(s), sub_question=s) for s in subs]
    return OrchestratorPlan(
        steps=steps,
        is_multi=True,
        reason=REWRITE_SUBQUESTIONS_PLAN_REASON,
    )


def _subs_are_cross_domain(sub_questions: list[str]) -> bool:
    tables = {_table_for_phrase(s) for s in sub_questions if (s or "").strip()}
    tables.discard(None)
    return len(tables) >= 2


def is_rewrite_multi(rewritten: object | None, original: str = "") -> bool:
    """True khi rewrite tách ≥2 sub_questions thực sự độc lập (domain/vế khác nhau)."""
    if rewritten is None:
        return False
    subs = getattr(rewritten, "sub_questions", None)
    if subs is None and isinstance(rewritten, dict):
        subs = rewritten.get("sub_questions")
    clean = [s.strip() for s in (subs or []) if (s or "").strip()]
    if len(clean) < 2:
        return False
    if _multi_question_heuristics(original, *clean):
        return True
    return _subs_are_cross_domain(clean)


def plan_orchestration(
    question: str,
    sub_questions: list[str] | None = None,
    original: str = "",
    intent: str = "",
) -> OrchestratorPlan:
    """Lập kế hoạch điều phối 1–2 bước chuyên gia (query_data | docs)."""
    clean_q = (question or "").strip()
    if not clean_q:
        return OrchestratorPlan(steps=[], is_multi=False, reason="Câu hỏi rỗng")

    for q in (clean_q, (original or "").strip()):
        if not q:
            continue
        if is_all_events_aggregate(q):
            return _plan_all_events_aggregate(q)
        cross = _plan_cross_domain_comparison(q)
        if cross:
            return cross
        diagram_docs = _plan_diagram_concept_docs(q)
        if diagram_docs:
            return diagram_docs

    if intent not in ("how_to", "troubleshoot", "concept", "chat", "clarify"):
        rewrite_plan = plan_from_rewrite_sub_questions(sub_questions or [], original=original)
        if rewrite_plan:
            return rewrite_plan

    if use_offline_tools():
        return _offline_plan_orchestration(clean_q)

    try:
        messages = [
            {"role": "system", "content": registry().render("orchestrator")},
            {"role": "user", "content": f"Câu hỏi của người dùng:\n{clean_q}"},
        ]
        return invoke_structured(messages, OrchestratorPlan, substep="orchestrator")
    except Exception:
        return _offline_plan_orchestration(clean_q)
