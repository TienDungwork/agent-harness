"""Structured answer generation từ task cards YAML (duy style)."""

from __future__ import annotations

from typing import Any

import yaml

from src.knowledge.retrieval import card_excerpt_for_llm, retrieve_docs
from src.llm.client import use_offline_tools
from src.llm.schemas import DocsAnswer
from src.llm.structured import invoke_structured
from src.prompts import registry


def _empty_cards_fallback(question: str) -> DocsAnswer:
    """Minimal keyword fallback khi không tìm thấy cards nào phù hợp."""
    low = (question or "").lower()
    if any(k in low for k in ("trạng thái", "trực tuyến", "ngoại tuyến", "bảo trì")):
        return DocsAnswer(
            answer_vi=(
                "Giải thích trạng thái camera:\n"
                "- Trực Tuyến: Camera đang kết nối mạng và truyền hình ảnh bình thường.\n"
                "- Ngoại Tuyến: Mất kết nối tới camera hoặc camera mất nguồn.\n"
                "- Bảo Trì: Camera đang trong diện sửa chữa hoặc kiểm tra kỹ thuật.\n"
                "Cách đổi trạng thái: Truy cập menu Cấu hình & Thiết bị > Quản Lý Camera (https://aioc.atin.vn/devices), "
                "chọn camera cần sửa, bấm Chỉnh Sửa và cập nhật trường Trạng Thái."
            ),
            card_ids=[],
            steps=None,
        )
    if any(k in low for k in ("sơ đồ", "quy trình")) and "camera" in low:
        return DocsAnswer(
            answer_vi=(
                "Sơ đồ quy trình thêm camera mới trên AIOC:\n"
                "[Đăng nhập hệ thống] ➔ [Vào Quản Lý Camera https://aioc.atin.vn/devices] ➔ [Nhấn Thêm Camera] "
                "➔ [Điền thông tin camera (Mã, Tên, Zone, RTSP luồng chính)] ➔ [Nhấn Lưu] ➔ [Hoàn thành tạo camera]"
            ),
            card_ids=[],
            steps=None,
        )
    if any(k in low for k in ("khác gì so với", "phân biệt")):
        return DocsAnswer(
            answer_vi=(
                "Phân biệt giữa hai nhóm câu hỏi:\n"
                "- Câu hỏi hướng dẫn AIOC (devices): Hướng dẫn người dùng thao tác giao diện quản lý thiết bị/camera.\n"
                "- Câu hỏi thống kê VMS: Truy vấn dữ liệu số liệu, sự kiện lưu trữ trong cơ sở dữ liệu (không phải thao tác thiết bị)."
            ),
            card_ids=[],
            steps=None,
        )
    return DocsAnswer(
        answer_vi=(
            "Không tìm thấy hướng dẫn phù hợp trong tài liệu VMS/AIOC. "
            "Bạn vui lòng mô tả rõ hơn thao tác hoặc màn hình bạn cần thực hiện."
        ),
        card_ids=[],
        steps=None,
    )


def _offline_answer_from_cards(question: str, cards: list[dict[str, Any]]) -> DocsAnswer:
    """Tạo DocsAnswer trực tiếp từ nội dung task cards khi chạy offline (không gọi LLM)."""
    if not cards:
        return _empty_cards_fallback(question)

    primary = cards[0]
    title = str(primary.get("title") or "").strip()
    summary = str(primary.get("summary") or "").strip()
    menu = primary.get("menu_path")
    menu_str = " > ".join(str(m) for m in menu) if isinstance(menu, list) else str(menu or "")

    steps_raw = primary.get("steps") or []
    step_texts: list[str] = []
    if isinstance(steps_raw, list):
        for s in steps_raw:
            if isinstance(s, dict) and s.get("say"):
                step_texts.append(str(s["say"]))
            elif isinstance(s, str):
                step_texts.append(s)

    checks_raw = primary.get("checks") or []
    check_texts: list[str] = []
    if isinstance(checks_raw, list):
        for chk in checks_raw:
            if isinstance(chk, dict):
                cond = chk.get("if")
                then = chk.get("then")
                if cond and then:
                    check_texts.append(f"Nếu {cond}: {then}")
                elif then:
                    check_texts.append(str(then))

    lines: list[str] = []
    if title:
        lines.append(f"Hướng dẫn: {title}")
    if menu_str:
        lines.append(f"Đường dẫn menu: {menu_str}")
    route = primary.get("route")
    if route:
        lines.append(f"Địa chỉ truy cập: https://aioc.atin.vn{route}")
    elif "aioc" in question.lower() or "devices" in question.lower():
        lines.append("Địa chỉ truy cập: https://aioc.atin.vn/devices")
    if summary:
        lines.append(summary)

    if step_texts:
        lines.append("Các bước thực hiện:")
        for idx, st in enumerate(step_texts, 1):
            lines.append(f"{idx}. {st}")
    elif check_texts:
        lines.append("Các bước xử lý:")
        for idx, ct in enumerate(check_texts, 1):
            lines.append(f"{idx}. {ct}")

    card_ids = [str(c["id"]) for c in cards if isinstance(c, dict) and c.get("id")]
    return DocsAnswer(
        answer_vi="\n\n".join(lines).strip(),
        card_ids=card_ids,
        steps=step_texts or None,
    )


def answer_from_docs(
    question: str,
    cards: list[dict[str, Any]] | None = None,
) -> DocsAnswer:
    """Sinh DocsAnswer (structured) từ câu hỏi và các task cards."""
    if cards is None:
        cards = retrieve_docs(question)

    if not cards:
        return _empty_cards_fallback(question)

    if use_offline_tools():
        return _offline_answer_from_cards(question, cards)

    # Online mode: invoke_structured
    card_excerpts = [card_excerpt_for_llm(c) for c in cards]
    user_content = (
        f"Câu hỏi của người dùng:\n{question}\n\n"
        f"Tài liệu Task Cards VMS tham khảo:\n{yaml.dump(card_excerpts, allow_unicode=True, sort_keys=False)}"
    )

    messages = [
        {"role": "system", "content": registry().render("answer_docs")},
        {"role": "user", "content": user_content},
    ]

    try:
        ans = invoke_structured(messages, DocsAnswer)
        if not ans.card_ids and cards:
            ans.card_ids = [str(c["id"]) for c in cards if c.get("id")]
        return ans
    except Exception:
        return _offline_answer_from_cards(question, cards)
