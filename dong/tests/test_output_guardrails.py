"""Unit tests for Phase 6: Output Guardrails (Hallucination Check, PII Redaction, Length Truncation)."""

from __future__ import annotations

import pytest
from src.guardrails import (
    _DISCLAIMER,
    _FALLBACK,
    check_output,
    redact_pii,
)


def test_redact_pii_phone_numbers():
    """Kiểm tra che giấu các định dạng số điện thoại phổ biến."""
    text = "Liên hệ anh Nam qua SĐT 0912345678 hoặc 0387654321."
    redacted = redact_pii(text)
    assert "0912345678" not in redacted
    assert "0387654321" not in redacted
    assert "[SĐT ẩn]" in redacted


def test_redact_pii_emails():
    """Kiểm tra che giấu địa chỉ email."""
    text = "Gửi báo cáo về admin@agent-atin.local và manager.kcn@hungphu.vn."
    redacted = redact_pii(text)
    assert "admin@agent-atin.local" not in redacted
    assert "manager.kcn@hungphu.vn" not in redacted
    assert "[email ẩn]" in redacted


def test_redact_pii_id_cards():
    """Kiểm tra che giấu số định danh CCCD/CMND."""
    text = "Khách có CCCD: 012345678901 và CMND 123456789 ra vào cổng."
    redacted = redact_pii(text)
    assert "012345678901" not in redacted
    assert "123456789" not in redacted
    assert "[CCCD ẩn]" in redacted


def test_check_output_verified_numbers_pass():
    """Kiểm tra câu trả lời có số liệu khớp 100% với evidence không bị gắn disclaimer."""
    evidence = ["Hôm nay có bao nhiêu lượt xe vào?", "total=150", "motorcycle=100", "car=50"]
    answer = "Tổng cộng có 150 lượt xe vào (trong đó 100 xe máy và 50 ô tô)."
    result = check_output(answer, evidence)

    assert result.valid is True
    assert _DISCLAIMER not in result.answer
    assert "unverified_numbers" not in result.issues


def test_check_output_formatted_numbers_with_dots_pass():
    """Kiểm tra số liệu có dấu chấm phân cách hàng nghìn (kiểu VN 1.250) vẫn khớp đúng."""
    evidence = ["Thống kê lượt xe", "total=1250"]
    answer = "Có 1.250 lượt xe đã qua cổng."
    result = check_output(answer, evidence)

    assert result.valid is True
    assert _DISCLAIMER not in result.answer


def test_check_output_unverified_numbers_adds_disclaimer():
    """Kiểm tra số liệu bịa đặt / hallucination bị phát hiện và gắn disclaimer."""
    evidence = ["Thống kê lượt xe", "total=150"]
    answer = "Có 150 lượt xe vào và 999 xe bị vi phạm tốc độ."
    result = check_output(answer, evidence)

    assert result.valid is False
    assert "unverified_numbers" in result.issues
    assert _DISCLAIMER in result.answer


def test_check_output_too_short_triggers_fallback():
    """Kiểm tra câu trả lời quá ngắn trả về fallback."""
    evidence = ["xe vào"]
    answer = "Ít."
    result = check_output(answer, evidence)

    assert result.valid is False
    assert "answer_too_short" in result.issues
    assert result.answer == _FALLBACK


def test_check_output_toxic_triggers_fallback():
    """Kiểm tra câu trả lời chứa từ ngữ toxic trả về fallback."""
    evidence = ["xe vào", "total=10"]
    answer = "Có 10 xe vào, đồ óc chó."
    result = check_output(answer, evidence)

    assert result.valid is False
    assert "toxic_output" in result.issues
    assert result.answer == _FALLBACK


def test_check_output_max_length_truncation(monkeypatch):
    """Kiểm tra giới hạn độ dài câu trả lời."""
    monkeypatch.setattr("src.guardrails.settings.guardrails_max_answer_len", 50)
    evidence = ["báo cáo"]
    answer = "A" * 100
    result = check_output(answer, evidence)

    assert "answer_too_long" in result.issues
    assert len(result.answer) <= 52  # 50 + ellipsis
    assert result.answer.endswith("…")
