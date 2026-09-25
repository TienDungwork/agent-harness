from agent.config.settings import get_settings


def test_connection_uses_kwargs_fields():
    s = get_settings()
    assert s.db_host
    assert s.db_port == 18644
    assert s.connect_timeout_seconds > 0
