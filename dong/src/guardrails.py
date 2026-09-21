"""Guardrail — input (chặn injection/toxic, lọc câu hỏi ngoài phạm vi)
+ output (đối chiếu số liệu chống hallucination, redact PII, giới hạn độ dài).

Toàn bộ logic guardrail sử dụng Regex và code thuần, KHÔNG gọi LLM
để tối ưu hóa tốc độ xử lý (< 1ms) và tiết kiệm chi phí.
"""

from __future__ import annotations

import re
from typing import Any

from src.config import settings

_INJECTION_PATTERNS = [
    re.compile(r"ignore (?:all |previous |above |prior )*(?:instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard (?:all |previous |above |prior )*(?:instructions|rules|prompts)", re.IGNORECASE),
    re.compile(r"bỏ qua (?:mọi |tất cả |các )*(?:hướng dẫn|chỉ dẫn|quy tắc|chỉ thị)", re.IGNORECASE),
    re.compile(r"quên (?:hết |mọi |tất cả |các )*(?:hướng dẫn|chỉ dẫn|quy tắc|lệnh trước)", re.IGNORECASE),
    re.compile(r"(?:reveal|dump|show|print|leak|get|output|display).*(?:system |developer )?(?:prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"(?:tiết lộ|in ra|hiển thị|cho xem|xem|xuất).*(?:system prompt|prompt hệ thống|chỉ dẫn hệ thống|hướng dẫn ban đầu)", re.IGNORECASE),
    re.compile(r"you are now (?:a|an|in) ", re.IGNORECASE),
    re.compile(r"act as (?:if you|a|an) ", re.IGNORECASE),
    re.compile(r"đóng vai (?:là|như|một) ", re.IGNORECASE),
    re.compile(r"(?:từ giờ|bây giờ) bạn là ", re.IGNORECASE),
    re.compile(r"\b(?:jailbreak|dan mode|developer mode enabled)\b", re.IGNORECASE),
    re.compile(r"bypass (?:all |safety |guardrail|security )*(?:filters|rules|checks)", re.IGNORECASE),
]

_TOXIC_WORDS = frozenset({"đụ", "địt", "đéo", "fuck", "shit", "cút", "óc chó", "dm", "dcm", "vcl"})

_PHONE = re.compile(r"(?:\+84|84|0)(?:3|5|7|8|9)\d{8}\b|\b0\d{9,10}\b")
_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_ID_CARD = re.compile(r"\b(?:CCCD|CMND|ID|Số định danh)[:\s]*(\d{9}|\d{12})\b", re.IGNORECASE)

# Từ khoá nhận diện phạm vi nghiệp vụ VMS KCN Hưng Phú (8 domain sự kiện)
STAT_KEYWORDS = frozenset(
    {
        # Giao thông & Phương tiện (Traffic / Plate)
        "xe",
        "xe máy",
        "xe may",
        "ô tô",
        "o to",
        "oto",
        "xe tải",
        "xe tai",
        "xe bus",
        "xe buýt",
        "xe buyt",
        "biển số",
        "bien so",
        "hãng xe",
        "hang xe",
        "lưu lượng",
        "luu luong",
        "lượt xe",
        "luot xe",
        "phương tiện",
        "phuong tien",
        "truy vết",
        "truy vet",
        "tìm xe",
        "tim xe",
        "vết xe",
        # Khuôn mặt & Con người (Smart Face)
        "khuôn mặt",
        "khuon mat",
        "nhận diện",
        "nhan dien",
        "gương mặt",
        "guong mat",
        "khách",
        "khach",
        "vip",
        "nhân viên",
        "nhan vien",
        "người lạ",
        "nguoi la",
        # Xâm nhập & Hàng rào ảo (Virtual Fence / Intrusion)
        "xâm nhập",
        "xam nhap",
        "hàng rào",
        "hang rao",
        "hàng rào ảo",
        "hang rao ao",
        "vượt rào",
        "vuot rao",
        "khu vực cấm",
        "khu vuc cam",
        "leo trèo",
        "leo treo",
        "hành lang",
        "hanh lang",
        # Cháy khói (Fire & Smoke)
        "cháy",
        "chay",
        "khói",
        "khoi",
        "hỏa hoạn",
        "hoa hoan",
        "báo cháy",
        "bao chay",
        "đám cháy",
        "dam chay",
        # Sự cố bất thường (Anomaly: Đám đông, ẩu đả, mực nước)
        "ẩu đả",
        "au da",
        "đánh nhau",
        "danh nhau",
        "đám đông",
        "dam dong",
        "tụ tập",
        "tu tap",
        "mực nước",
        "muc nuoc",
        "ngập",
        "ngap",
        "ngập úng",
        "ngap ung",
        "nước dâng",
        "nuoc dang",
        "bất thường",
        "bat thuong",
        "sự cố",
        "su co",
        # Thống kê chung & Địa điểm VMS
        "khu vực",
        "khu vuc",
        "ra vào",
        "ra/vào",
        "ra vao",
        "lượt vào",
        "luot vao",
        "lượt ra",
        "luot ra",
        "thống kê",
        "thong ke",
        "báo cáo",
        "bao cao",
        "bao nhiêu người",
        "bao nhiêu xe",
        "bao nhiêu lượt",
        "số lượt",
        "so luot",
        "cổng",
        "cong",
        "camera",
        "cam",
        "khung giờ",
        "khung gio",
        "kcn",
        "hưng phú",
        "hung phu",
        "khu a",
        "khu b",
        "khu c",
        # AIOC Cloud Cam — hướng dẫn dùng web /devices + vẽ sơ đồ
        "aioc",
        "atin.vn",
        "cloud cam",
        "devices",
        "quản lý camera",
        "quan ly camera",
        "thiết bị",
        "thiet bi",
        "đăng nhập",
        "dang nhap",
        "sơ đồ",
        "so do",
        "flowchart",
        "mermaid",
        "luồng chính",
        "luong chinh",
        "trực tuyến",
        "truc tuyen",
        "ngoại tuyến",
        "ngoai tuyen",
        "bảo trì",
        "bao tri",
    }
)

OUT_OF_SCOPE_REPLY = (
    "Xin lỗi, câu hỏi này ngoài phạm vi hỗ trợ. Tôi hỗ trợ thống kê sự kiện VMS "
    "KCN Hưng Phú, hướng dẫn dùng AIOC (https://aioc.atin.vn/devices), và vẽ sơ đồ "
    "các bước thao tác liên quan. "
    'Hãy hỏi ví dụ: "Hôm nay có bao nhiêu lượt xe vào?" hoặc '
    '"Làm sao mở Quản Lý Camera trên AIOC?".'
)

_FALLBACK = "Xin lỗi, tôi chưa đủ dữ liệu đáng tin để trả lời. Hãy hỏi lại rõ hơn."
_DISCLAIMER = " (Lưu ý: số liệu chưa xác minh được với dữ liệu tool trả về.)"
EMPTY_TOOL_REPLY = "Không có dữ liệu khớp câu hỏi trong khoảng thời gian/điều kiện đã cho."


class GuardrailViolation(Exception):
    """Injection/nội dung độc hại — chặn cứng (raise HTTP 400)."""

    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(reason)


class OutputCheckResult:
    __slots__ = ("valid", "issues", "answer")

    def __init__(self, valid: bool, issues: list[str] | None = None, answer: str = ""):
        self.valid = valid
        self.issues = issues or []
        self.answer = answer


def detect_prompt_injection(text: str) -> bool:
    return any(p.search(text or "") for p in _INJECTION_PATTERNS)


def detect_toxicity(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in _TOXIC_WORDS)


def redact_pii(text: str) -> str:
    """Che giấu thông tin cá nhân nhạy cảm (SĐT, Email, CCCD/CMND)."""
    if not text:
        return ""
    text = _PHONE.sub("[SĐT ẩn]", text)
    text = _EMAIL.sub("[email ẩn]", text)
    text = _ID_CARD.sub(lambda m: m.group(0).replace(m.group(1), "[CCCD ẩn]"), text)
    return text


def in_scope(question: str) -> bool:
    low = (question or "").lower()
    return any(k in low for k in STAT_KEYWORDS)


def check_input(text: str) -> None:
    """Raise GuardrailViolation nếu injection hoặc toxic."""
    if detect_prompt_injection(text):
        raise GuardrailViolation("prompt_injection_detected", {"pattern_match": True})
    if detect_toxicity(text):
        raise GuardrailViolation("unsafe_content", {"pattern_match": True})


def check_output(answer: str, evidence: list[str], *, tool_empty: bool = False) -> OutputCheckResult:
    """Đối chiếu số liệu thật từ evidence để chống hallucination,
    che giấu PII và giới hạn độ dài câu trả lời.
    """
    issues: list[str] = []
    text = answer or ""

    if len(text) < settings.guardrails_min_answer_len:
        issues.append("answer_too_short")
    if detect_toxicity(text):
        issues.append("toxic_output")

    if "answer_too_short" in issues or "toxic_output" in issues:
        return OutputCheckResult(valid=False, issues=issues, answer=_FALLBACK)

    # Chuẩn hoá dấu phân cách hàng nghìn (chấm/phẩy giữa các chữ số) để so khớp số liệu
    context_text = " ".join(str(e) for e in evidence if e)
    normalized_context = re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", context_text)
    normalized_answer = re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", text)

    # Trích xuất toàn bộ số từ câu trả lời
    numbers = re.findall(r"\b\d+\b", normalized_answer)
    unverified = [n for n in numbers if n not in normalized_context]

    if unverified:
        if tool_empty:
            issues.append("fabricated_numbers_on_empty_tool")
            text = EMPTY_TOOL_REPLY
        else:
            issues.append("unverified_numbers")
            text = text.rstrip() + _DISCLAIMER

    redacted = redact_pii(text)
    if redacted != text:
        issues.append("pii_redacted")
        text = redacted

    max_len = settings.guardrails_max_answer_len
    if max_len and len(text) > max_len:
        issues.append("answer_too_long")
        text = text[:max_len].rstrip() + "…"

    return OutputCheckResult(valid=len(issues) == 0, issues=issues, answer=text)

def _is_tool_empty(query: Any) -> bool:
    if query is None:
        return False
        
    if getattr(query, "row_count", None) == 0:
        return True
        
    rows = getattr(query, "rows", None)
    if rows is not None and len(rows) == 0:
        return True
        
    if rows:
        has_numeric = False
        all_numeric_zero = True
        
        for row in rows:
            for cell in row:
                if isinstance(cell, (int, float)):
                    has_numeric = True
                    if cell != 0:
                        all_numeric_zero = False
                elif isinstance(cell, str):
                    try:
                        val = float(cell)
                        has_numeric = True
                        if val != 0:
                            all_numeric_zero = False
                    except ValueError:
                        pass
                        
        if has_numeric and all_numeric_zero:
            return True
            
        return False
        
    return False
