#!/usr/bin/env python3
"""Patch OpenHands/Creanova SDK so custom gateways never receive stream_options.

Canvas overlay cannot stop the image SDK from injecting
``stream_options={"include_usage": True}`` when ``llm.stream`` is true.
Strict OpenAI-compatible gateways (LAN Pydantic proxies) reject that field
with 400 ``param=stream_options``.

The Hub image's ``openhands-agent-server`` is a PyInstaller binary, so
editing site-packages is not enough unless we also start the server via
system Python. This script:

1. Tries to patch ``llm.py`` on disk (sudo if needed).
2. Monkeypatches ``LLM._prepare_transport_kwargs`` in-process.
3. With ``--run-agent-server``, starts ``python -m openhands.agent_server``
   in the same process so the monkeypatch applies.

Idempotent. Safe to run on every container start.
"""

from __future__ import annotations

import importlib
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path


NEEDLE = """        if enable_streaming:
            kwargs.setdefault("stream_options", {"include_usage": True})
"""

REPLACEMENT = """        if enable_streaming and not getattr(self, "base_url", None):
            kwargs.setdefault("stream_options", {"include_usage": True})
        elif enable_streaming:
            extra_drop = list(kwargs.get("additional_drop_params") or [])
            if "stream_options" not in extra_drop:
                extra_drop.append("stream_options")
            kwargs["additional_drop_params"] = extra_drop
            kwargs.pop("stream_options", None)
"""

CANDIDATES = (
    Path("/usr/local/lib/python3.13/site-packages/openhands/sdk/llm/llm.py"),
    Path("/usr/local/lib/python3.12/site-packages/openhands/sdk/llm/llm.py"),
    Path("/usr/local/lib/python3.13/site-packages/Creanova/sdk/llm/llm.py"),
    Path("/usr/local/lib/python3.12/site-packages/Creanova/sdk/llm/llm.py"),
)

_PATCH_ATTR = "_drop_stream_options_on_custom_base_url"


def discover_llm_files() -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    roots = [
        Path("/usr/local/lib"),
        Path("/agent-server/.venv/lib"),
        Path("/usr/lib"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for pkg in ("openhands", "Creanova"):
            for path in root.glob(f"python3.*/site-packages/{pkg}/sdk/llm/llm.py"):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    found.append(path)
    for path in CANDIDATES:
        if path.is_file() and path not in seen:
            seen.add(path)
            found.append(path)
    return found


def _write_text(path: Path, text: str) -> None:
    if os.access(path, os.W_OK):
        path.write_text(text, encoding="utf-8")
        return
    fd, tmp = tempfile.mkstemp(suffix=".py")
    try:
        os.write(fd, text.encode("utf-8"))
        os.close(fd)
        fd = -1
        result = subprocess.run(
            ["sudo", "-n", "cp", tmp, str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PermissionError(result.stderr.strip() or "sudo cp failed")
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass


def patch_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if REPLACEMENT in text:
        return "already-patched"
    if NEEDLE not in text:
        return "needle-missing"
    try:
        _write_text(path, text.replace(NEEDLE, REPLACEMENT, 1))
    except OSError as exc:
        return f"write-failed:{exc}"
    return "patched"


def _strip_stream_options(result: dict, enable_streaming: bool, base_url: object) -> dict:
    if not enable_streaming or not base_url:
        return result
    result.pop("stream_options", None)
    extra_drop = list(result.get("additional_drop_params") or [])
    if "stream_options" not in extra_drop:
        extra_drop.append("stream_options")
    result["additional_drop_params"] = extra_drop
    return result


def apply_runtime_monkeypatch() -> int:
    patched = 0
    for mod_name in ("openhands.sdk.llm.llm", "Creanova.sdk.llm.llm"):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        cls = getattr(mod, "LLM", None)
        if cls is None:
            continue
        orig = cls._prepare_transport_kwargs
        if getattr(orig, _PATCH_ATTR, False):
            patched += 1
            continue

        def _wrapped(self, *args, _orig=orig, **kwargs):
            result = _orig(self, *args, **kwargs)
            enable_streaming = bool(kwargs.get("enable_streaming", False))
            return _strip_stream_options(
                result, enable_streaming, getattr(self, "base_url", None)
            )

        setattr(_wrapped, _PATCH_ATTR, True)
        cls._prepare_transport_kwargs = _wrapped
        patched += 1
        print(
            f"[agent-canvas] stream_options monkeypatch: {mod_name}",
            file=sys.stderr,
        )
    return patched


def patch_files() -> int:
    paths = discover_llm_files()
    if not paths:
        print("[agent-canvas] stream_options file patch: no llm.py found", file=sys.stderr)
        return 0
    failed = False
    for path in paths:
        status = patch_file(path)
        print(f"[agent-canvas] stream_options file patch {path}: {status}", file=sys.stderr)
        if status not in {"patched", "already-patched"}:
            failed = True
    return 1 if failed else 0


def run_agent_server(argv: list[str]) -> None:
    patch_files()
    n = apply_runtime_monkeypatch()
    if n == 0:
        print(
            "[agent-canvas] WARNING: LLM class not found; stream_options guard skipped",
            file=sys.stderr,
        )
    port = "18000"
    extra: list[str] = []
    args = list(argv)
    while args:
        token = args.pop(0)
        if token == "--port" and args:
            port = args.pop(0)
        elif token.startswith("--port="):
            port = token.split("=", 1)[1]
        else:
            extra.append(token)
    for mod in ("openhands.agent_server", "Creanova.agent_server"):
        try:
            importlib.import_module(mod)
        except ImportError:
            continue
        sys.argv = [mod, "--port", port, *extra]
        print(
            f"[agent-canvas] starting {mod} on port {port} (system Python)",
            file=sys.stderr,
        )
        runpy.run_module(mod, run_name="__main__", alter_sys=True)
        return
    raise SystemExit("Cannot import openhands.agent_server or Creanova.agent_server")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--run-agent-server":
        run_agent_server(argv[1:])
        return 0
    return patch_files()


if __name__ == "__main__":
    raise SystemExit(main())

if os.environ.get("CREANOVA_APPLY_STREAM_OPTIONS_PATCH", "").lower() in (
    "1",
    "true",
):
    try:
        apply_runtime_monkeypatch()
    except Exception as exc:  # pragma: no cover - startup guard
        print(
            f"[agent-canvas] stream_options monkeypatch failed: {exc}",
            file=sys.stderr,
        )
