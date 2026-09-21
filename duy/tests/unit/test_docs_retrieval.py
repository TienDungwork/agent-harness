from agent.knowledge.loader import load_published_cards
from agent.knowledge.retrieval import retrieve_docs


def test_loader_has_published_cards():
    cards = load_published_cards()
    assert len(cards) >= 30
    assert all(c.get("status") == "published" for c in cards)


def test_retrieve_add_camera():
    hits = retrieve_docs("Làm sao để thêm camera?")
    assert hits
    assert hits[0]["id"] == "devices.add_camera"


def test_retrieve_live_stream_issue():
    hits = retrieve_docs("Không xem được live camera bị đen")
    assert hits
    assert hits[0]["id"] == "troubleshooting.live_stream_unavailable"


def test_retrieve_howto_view_motorbike_count():
    hits = retrieve_docs(
        "làm thế nào để xem có bao nhiêu xe máy trong ngày hôm nay"
    )
    assert hits
    assert hits[0]["id"] == "how-to.ai.search-plate-history"
