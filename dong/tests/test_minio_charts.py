from src.infra.storage import minio_charts


def test_upload_chart_png_builds_chatbot_key(monkeypatch):
    captured: dict = {}

    class _FakeClient:
        def put_object(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        minio_charts.settings,
        "minio_endpoint",
        "http://192.168.1.198:9200",
    )
    monkeypatch.setattr(minio_charts.settings, "minio_access_key", "admin")
    monkeypatch.setattr(minio_charts.settings, "minio_secret_key", "secret")
    monkeypatch.setattr(minio_charts.settings, "minio_bucket", "chatbot-images")
    monkeypatch.setattr(minio_charts.settings, "minio_chart_prefix", "chatbot")
    monkeypatch.setattr(
        minio_charts.settings,
        "minio_public_base_url",
        "http://192.168.1.198:9200",
    )
    monkeypatch.setattr(
        minio_charts.boto3,
        "client",
        lambda *_a, **_k: _FakeClient(),
    )
    monkeypatch.setattr(
        minio_charts.uuid,
        "uuid4",
        lambda: type("U", (), {"hex": "abc123"})(),
    )

    url = minio_charts.upload_chart_png(b"png-bytes", session_id="sess1")
    assert captured["Bucket"] == "chatbot-images"
    assert captured["Key"].startswith("chatbot/sess1/")
    assert captured["Key"].endswith(".png")
    assert captured["ContentType"] == "image/png"
    assert url == "http://192.168.1.198:9200/chatbot-images/chatbot/sess1/abc123.png"


def test_upload_chart_png_requires_config(monkeypatch):
    monkeypatch.setattr(minio_charts.settings, "minio_endpoint", "")
    monkeypatch.setattr(minio_charts.settings, "minio_access_key", "")
    try:
        minio_charts.upload_chart_png(b"x", session_id="s")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "MinIO" in str(e)
