from agent.catalog.retrieval import _tokens, force_dataset_id, retrieve_datasets


def test_oto_phrase_kept_as_token():
    tokens = _tokens("ngày 13/09/2026 có bao nhiêu ô tô, bao nhiêu xe máy ra vào")
    assert "ô tô" in tokens
    assert "xe máy" in tokens
    assert "tô" not in tokens


def test_vehicle_in_out_forces_its_not_face():
    q = "ngày 13/09/2026 có bao nhiêu ô tô, bao nhiêu xe máy ra vào"
    assert force_dataset_id(q) == "its.plate_events"
    ids = [d["id"] for d in retrieve_datasets(q)]
    assert ids == ["its.plate_events"]


def test_face_attendance_still_smart_face():
    q = "Hôm nay bao nhiêu lượt khuôn mặt chấm công?"
    assert force_dataset_id(q) == "smart_face.events"
    assert retrieve_datasets(q)[0]["id"] == "smart_face.events"


def test_bare_ra_vao_without_vehicle_does_not_force_its():
    # Không còn alias "ra vào" trần trên face; không ép ITS nếu không có từ xe.
    assert force_dataset_id("Có bao nhiêu lượt ra vào?") is None


EVAL_ROUTING = [
    ("Có bao nhiêu camera đang hoạt động?", "vms.cameras"),
    ("Có bao nhiêu camera phương tiện?", "its.plate_events"),
    ("Hôm nay bao nhiêu sự kiện bất thường?", "anomaly.events"),
    ("ngày 13/09/2026 có bao nhiêu ô tô, bao nhiêu xe máy ra vào", "its.plate_events"),
    ("Top camera có nhiều biển số nhất?", "its.plate_events"),
]


def test_eval_routing_pack():
    for question, expected_id in EVAL_ROUTING:
        ids = [d["id"] for d in retrieve_datasets(question)]
        assert ids[0] == expected_id, f"{question!r} → {ids}, expect {expected_id}"
