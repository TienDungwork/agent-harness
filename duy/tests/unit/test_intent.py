from agent.graph.nodes.classify_intent import parse_intent_payload
from agent.graph.nodes.respond import try_format_simple_answer


def test_parse_json_intent():
    intent, reason, answer = parse_intent_payload(
        '{"intent":"chat","reason":"chào hỏi xã giao","answer":"Xin chào!"}'
    )
    assert intent == "chat"
    assert "chào" in reason
    assert answer.startswith("Xin chào")


def test_parse_query_db_clears_answer():
    intent, _, answer = parse_intent_payload(
        '```json\n{"intent":"query_db","reason":"đếm camera","answer":"không dùng"}\n```'
    )
    assert intent == "query_db"
    assert answer == ""


def test_parse_how_to_clears_answer():
    intent, _, answer = parse_intent_payload(
        '{"intent":"how_to","reason":"hướng dẫn thêm camera","answer":"bịa"}'
    )
    assert intent == "how_to"
    assert answer == ""


def test_parse_token_fallback():
    intent, reason, answer = parse_intent_payload("out_of_scope")
    assert intent == "out_of_scope"
    assert reason == "parsed-from-text"
    assert answer == ""


def test_unparsed_defaults_to_clarify_not_query():
    intent, reason, answer = parse_intent_payload("mình cũng không rõ nữa")
    assert intent == "clarify"
    assert reason == "unparsed-intent"
    assert answer


def test_simple_format_camera_count():
    text = try_format_simple_answer(
        "Có bao nhiêu camera đang hoạt động?",
        {"row_count": 1, "rows": [{"count": 6}]},
    )
    assert text == "Có 6 camera đang hoạt động."


def test_parse_howto_view_count_prefers_how_to_label():
    # Parser chỉ kiểm JSON; rule nằm ở prompt — đảm bảo how_to được phép.
    intent, _, answer = parse_intent_payload(
        '{"intent":"how_to","reason":"hỏi cách xem số xe máy","answer":"x"}'
    )
    assert intent == "how_to"
    assert answer == ""


def test_parse_web_search_clears_answer():
    intent, _, answer = parse_intent_payload(
        '{"intent":"web_search","reason":"hỏi định nghĩa ALPR","answer":"bịa"}'
    )
    assert intent == "web_search"
    assert answer == ""


def test_simple_format_moto_today():
    text = try_format_simple_answer(
        "Hôm nay có bao nhiêu xe máy?",
        {"row_count": 1, "rows": [{"count": 0}]},
    )
    assert text == "Có 0 lượt xe máy hôm nay."
