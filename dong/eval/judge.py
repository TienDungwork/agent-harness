"""Judge nhẹ 1–5 — bám nguồn, tiếng Việt, không bịa số (không RAGAS)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.llm import invoke_text, use_offline_tools

@dataclass
class JudgeScore:
    score: int
    reason: str

_SYSTEM = """Bạn là giám khảo đánh giá chất lượng câu trả lời của trợ lý AI.
Chấm điểm từ 1 đến 5 dựa trên các tiêu chí:
- Bám sát nguồn (evidence) được cung cấp.
- Sử dụng tiếng Việt rõ ràng, tự nhiên.
- Tuyệt đối KHÔNG bịa số liệu (hallucination).

Bạn chỉ được phép trả về duy nhất một đối tượng JSON với định dạng sau (không chứa markdown, không có giải thích thừa):
{"score": <số nguyên từ 1 đến 5>, "reason": "<lý do chấm điểm ngắn gọn bằng tiếng Việt>"}"""

def judge_answer(question: str, answer: str, *, evidence: str = "", expected: str = "") -> JudgeScore:
    if use_offline_tools():
        return JudgeScore(0, "skipped (offline/pytest)")
        
    prompt = f"Câu hỏi: {question}\nCâu trả lời: {answer}\n"
    if evidence:
        prompt += f"Nguồn (evidence): {evidence}\n"
    if expected:
        prompt += f"Câu trả lời kỳ vọng: {expected}\n"
        
    try:
        res = invoke_text(system_prompt=_SYSTEM, user_prompt=prompt)
        match = re.search(r'\{.*\}', res, re.DOTALL)
        if not match:
            return JudgeScore(0, "parse_error: no json found")
        
        data = json.loads(match.group(0))
        score = int(data.get("score", 0))
        if not 1 <= score <= 5:
            return JudgeScore(0, f"parse_error: invalid score {score}")
        reason = str(data.get("reason", ""))
        return JudgeScore(score, reason)
    except Exception as e:
        return JudgeScore(0, f"error: {str(e)}")
