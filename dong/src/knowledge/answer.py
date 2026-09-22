"""Structured answer generation từ task cards YAML (duy style)."""

from __future__ import annotations

from typing import Any

import yaml

from src.knowledge.retrieval import card_excerpt_for_llm, retrieve_docs
from src.llm.client import use_offline_tools
from src.llm.schemas import DocsAnswer
from src.llm.structured import invoke_structured

DOCS_SYSTEM_PROMPT = """Bạn là trợ lý hướng dẫn sử dụng hệ thống VMS (Video Management System).
Nhiệm vụ: Trả lời câu hỏi của người dùng CHỈ dựa vào các task cards được cung cấp.

Quy tắc bắt buộc:
1. Chỉ dùng thông tin trong task cards (summary, steps, checks, menu_path, preconditions).
2. Không bịa thêm menu, nút bấm, trường dữ liệu ngoài tài liệu.
3. Trả lời bằng tiếng Việt, súc tích, theo từng bước rõ ràng.
4. Nếu có menu_path, nêu rõ đường dẫn menu ở đầu.
5. Nếu có preconditions quan trọng, nhắc người dùng trước khi thao tác.
6. Với troubleshooting: trình bày rõ điều kiện (nếu... thì...).
7. Tuyệt đối không đề cập đến SQL, cơ sở dữ liệu hay query backend.
8. Điền đầy đủ trường card_ids chứa mã định danh (id) của các card được sử dụng.
9. Điền danh sách steps tóm tắt các bước chính (nếu câu hỏi là dạng how_to)."""


def _offline_answer_from_cards(question: str, cards: list[dict[str, Any]]) -> DocsAnswer:
    """Tạo DocsAnswer trực tiếp từ nội dung task cards khi chạy offline (không gọi LLM)."""
    if not cards:
        return DocsAnswer(
            answer_vi=(
                "Không tìm thấy hướng dẫn phù hợp trong tài liệu VMS. "
                "Bạn vui lòng mô tả rõ hơn thao tác hoặc màn hình bạn cần thực hiện."
            ),
            card_ids=[],
            steps=None,
        )

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
        return DocsAnswer(
            answer_vi=(
                "Không tìm thấy hướng dẫn phù hợp trong tài liệu VMS. "
                "Bạn vui lòng mô tả rõ hơn thao tác hoặc màn hình bạn cần thực hiện."
            ),
            card_ids=[],
            steps=None,
        )

    if use_offline_tools():
        return _offline_answer_from_cards(question, cards)

    # Online mode: invoke_structured
    card_excerpts = [card_excerpt_for_llm(c) for c in cards]
    user_content = (
        f"Câu hỏi của người dùng:\n{question}\n\n"
        f"Tài liệu Task Cards VMS tham khảo:\n{yaml.dump(card_excerpts, allow_unicode=True, sort_keys=False)}"
    )

    messages = [
        {"role": "system", "content": DOCS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        ans = invoke_structured(messages, DocsAnswer)
        if not ans.card_ids and cards:
            ans.card_ids = [str(c["id"]) for c in cards if c.get("id")]
        return ans
    except Exception:
        return _offline_answer_from_cards(question, cards)
