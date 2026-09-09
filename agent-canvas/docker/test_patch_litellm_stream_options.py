"""Needle replacement for the container SDK stream_options patcher."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch_litellm_stream_options import (  # noqa: E402
    NEEDLE,
    REPLACEMENT,
    _strip_stream_options,
    patch_file,
)


def test_patch_file_replaces_needle(tmp_path: Path):
    target = tmp_path / "llm.py"
    target.write_text("prefix\n" + NEEDLE + "suffix\n", encoding="utf-8")
    assert patch_file(target) == "patched"
    text = target.read_text(encoding="utf-8")
    assert REPLACEMENT in text
    assert NEEDLE not in text
    assert patch_file(target) == "already-patched"


def test_strip_stream_options_only_when_base_url_and_streaming():
    payload = {"stream_options": {"include_usage": True}}
    stripped = _strip_stream_options(dict(payload), True, "http://192.168.1.196:18083/v1")
    assert "stream_options" not in stripped
    assert "stream_options" in stripped["additional_drop_params"]

    kept = _strip_stream_options(dict(payload), True, None)
    assert kept["stream_options"] == {"include_usage": True}
