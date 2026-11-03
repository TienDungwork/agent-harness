"""Thông báo lỗi thân thiện cho API chat/ask/stream."""

from __future__ import annotations

USER_ERROR_MAX_LEN = 240


def short_user_error(message: str) -> str:
    msg = (message or "").strip()
    if len(msg) <= USER_ERROR_MAX_LEN:
        return msg
    return msg[: USER_ERROR_MAX_LEN - 1].rstrip() + "…"


def format_error_message(exc: Exception) -> str:
    err_str = str(exc).lower()
    if any(k in err_str for k in ("clickhouse", "ch timeout")):
        return short_user_error(
            "Lỗi cơ sở dữ liệu phân tích: không truy vấn được số liệu. Kiểm tra ClickHouse."
        )
    if any(k in err_str for k in ("database", "postgres", "psycopg2", "could not connect to server", "connection refused to server")):
        return short_user_error(
            "Lỗi cơ sở dữ liệu VMS: không truy vấn được số liệu. Kiểm tra dịch vụ database."
        )
    if any(k in err_str for k in ("timeout", "timed out", "connection error", "connection refused", "apiconnectionerror", "connect error")):
        return short_user_error(
            "Lỗi mô hình AI: quá thời gian chờ hoặc máy chủ không phản hồi. Thử lại sau."
        )
    if any(k in err_str for k in ("rate limit", "429", "quota", "too many requests")):
        return short_user_error("Mô hình AI đang bận (rate limit). Vui lòng thử lại sau giây lát.")
    if any(k in err_str for k in ("llm structured", "parse", "schema", "validationerror")):
        return short_user_error("Mô hình AI trả về sai định dạng. Thử lại với cách diễn đạt khác.")
    if (
        any(k in err_str for k in ("thiếu biến", "template rỗng", "placeholder", "render prompt"))
        or ("prompt" in err_str and any(k in err_str for k in ("thiếu", "rỗng", "template", "biến", "placeholder")))
    ):
        return short_user_error(
            "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
        )
    if any(k in err_str for k in ("lỗi tạo sql", "lỗi validate sql", "vượt quá số lần sửa", "select ", " from ")):
        return short_user_error("Không tạo được truy vấn dữ liệu phù hợp. Thử câu hỏi đơn giản hơn.")
    if any(k in err_str for k in ("lỗi truy vấn cơ sở dữ liệu", "lỗi execute")):
        return short_user_error("Lỗi thực thi truy vấn. Tạm thời không lấy được số liệu. Thử lại sau.")
    return short_user_error("Không thể xử lý câu hỏi lúc này. Vui lòng thử lại hoặc diễn đạt khác.")
