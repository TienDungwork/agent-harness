"""Unit tests — batch SQL sub-questions."""

from __future__ import annotations

from src.agent.sql_batch import (
    build_sql_batch,
    execute_sql_batch,
    offline_sql_for_sub_question,
)


def test_offline_sql_per_sub_question_domain():
    plate = offline_sql_for_sub_question("Hôm nay có bao nhiêu sự kiện phương tiện?")
    zone = offline_sql_for_sub_question("Hôm nay có bao nhiêu sự kiện vùng cấm?")
    face = offline_sql_for_sub_question("Hôm nay có bao nhiêu sự kiện khuôn mặt?")
    anomaly = offline_sql_for_sub_question("Hôm nay có bao nhiêu sự kiện bất thường?")
    ranged = offline_sql_for_sub_question(
        "Trong khoảng từ 23/09/2026 đến 24/09/2026, có bao nhiêu sự kiện phương tiện?"
    )
    assert "plate_event" in plate
    assert "zone_event" in zone
    assert "smf_face_events" in face
    assert "access_time" in face
    assert "anomaly_event" in anomaly
    assert "BETWEEN DATE '2026-09-23'" in ranged
    assert "organization_id" in plate


def test_build_sql_batch_offline_two_queries():
    subs = [
        "Trong ngày hôm nay, có bao nhiêu sự kiện phương tiện?",
        "Trong ngày hôm nay, có bao nhiêu sự kiện vùng cấm?",
    ]
    batch = build_sql_batch(subs)
    assert len(batch) == 2
    assert "plate_event" in batch[0]["sql"]
    assert "zone_event" in batch[1]["sql"]


def test_execute_sql_batch_returns_per_sub_question():
    subs = [
        "Trong ngày hôm nay, có bao nhiêu sự kiện phương tiện?",
        "Trong ngày hôm nay, có bao nhiêu sự kiện vùng cấm?",
    ]
    batch = build_sql_batch(subs)
    results = execute_sql_batch(batch)
    assert len(results) == 2
    assert results[0]["rows"]
    assert results[1]["rows"]
