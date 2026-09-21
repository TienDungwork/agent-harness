from agent.catalog.retrieval import retrieve_datasets
from agent.config.settings import Settings, get_settings


def test_env_defaults_match_chosen_stack():
    s = get_settings()
    assert s.llm_model == "qwen3-16k-nothink"
    assert s.db_host == "192.168.1.200"
    assert s.db_port == 18644
    assert s.db_user == "vinhdq"


def test_settings_no_single_dbname():
    assert not hasattr(Settings, "db_name") or "db_name" not in Settings.model_fields


def test_camera_question_hits_vms_cameras():
    ids = [d["id"] for d in retrieve_datasets("Có bao nhiêu camera đang hoạt động?")]
    assert ids[0] == "vms.cameras"


def test_anomaly_question_hits_anomaly():
    ids = [d["id"] for d in retrieve_datasets("Hôm nay bao nhiêu sự kiện bất thường?")]
    assert "anomaly.events" in ids


def test_vehicle_camera_question_hits_its_not_vms_camera():
    datasets = retrieve_datasets("Có bao nhiêu camera phương tiện?")
    ids = [d["id"] for d in datasets]
    assert ids[0] == "its.plate_events"
    assert all(d["database"] == "its" for d in datasets)
    assert "vms.cameras" not in ids


def test_plain_camera_count_stays_on_vms():
    datasets = retrieve_datasets("Có bao nhiêu camera?")
    ids = [d["id"] for d in datasets]
    assert ids[0] == "vms.cameras"
    assert all(d["database"] == "vms_db" for d in datasets)


def test_active_camera_question_does_not_include_ai_event():
    ids = [d["id"] for d in retrieve_datasets("Có bao nhiêu camera đang hoạt động?")]
    assert ids[0] == "vms.cameras"
    assert "vms.ai_events" not in ids
