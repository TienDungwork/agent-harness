import json
from unittest.mock import patch

from agent.services.searxng_service import format_web_excerpt, search_web


def test_format_web_excerpt():
    text = format_web_excerpt(
        [
            {"title": "ALPR", "url": "https://example.com/a", "content": "Automatic plate recognition"},
            {"title": "Wiki", "url": "https://example.com/b", "content": "More info"},
        ]
    )
    assert "ALPR" in text
    assert "https://example.com/a" in text


def test_search_web_parses_json():
    payload = {
        "results": [
            {"title": "Test", "url": "https://a.test", "content": "snippet", "engine": "duckduckgo"},
            {"title": "No URL"},
        ]
    }
    body = json.dumps(payload).encode()

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        out = search_web("ALPR là gì")

    assert out["result_count"] == 1
    assert out["results"][0]["url"] == "https://a.test"
