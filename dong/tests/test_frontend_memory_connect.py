"""Unit and contract tests for Frontend Memory & Cache Hit connection (Phase 4 — Connect UI to data).

Validates:
1. index.html contains #memory-status-badge, #memory-status-text, and #btn-reset-memory.
2. style.css defines .badge-cache-hit, .btn-reset-memory, and .memory-badge.
3. app.js binds #btn-reset-memory to handleResetMemory.
4. handleResetMemory issues DELETE /api/memory?user_id=... and resets UI counter to 0.
5. app.js displays badge '⚡ Cache Hit' with class .badge-cache-hit when payload contains cache_hit: true.
6. fetchUserMemoryStatus fetches GET /api/memory?user_id=... and syncs facts count to UI.
7. Frontend static files (HTML, JS, CSS) are served with HTTP 200.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient

from src.main import app

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
APP_JS = FRONTEND_DIR / "app.js"
STYLE_CSS = FRONTEND_DIR / "style.css"


@pytest.fixture
def client():
    return TestClient(app)


def test_index_html_has_memory_elements():
    """index.html phải có đủ các element giao diện bộ nhớ (badge status và nút reset memory)."""
    assert INDEX_HTML.exists(), "frontend/index.html không tồn tại"
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="memory-status-badge"' in html, "Thiếu element #memory-status-badge trong index.html"
    assert 'id="memory-status-text"' in html, "Thiếu element #memory-status-text trong index.html"
    assert 'id="btn-reset-memory"' in html, "Thiếu element #btn-reset-memory trong index.html"
    assert "Reset Memory" in html, "Thiếu nhãn 'Reset Memory' trong index.html"


def test_style_css_has_memory_and_cache_badge_styles():
    """style.css phải chứa CSS selectors cho badge bộ nhớ, nút reset và huy hiệu Cache Hit."""
    assert STYLE_CSS.exists(), "frontend/style.css không tồn tại"
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".memory-badge" in css, "Thiếu class .memory-badge trong style.css"
    assert ".btn-reset-memory" in css, "Thiếu class .btn-reset-memory trong style.css"
    assert ".badge-cache-hit" in css, "Thiếu class .badge-cache-hit trong style.css"
    # Kiểm tra màu sắc đặc trưng teal/cyan của Cache Hit
    assert "0d9488" in css or "10b981" in css, "style.css phải có màu nhận diện cho badge-cache-hit"


def test_app_js_wires_btn_reset_memory_to_handleResetMemory():
    """app.js phải map btnResetMemory từ DOM và gán sự kiện click handleResetMemory."""
    assert APP_JS.exists(), "frontend/app.js không tồn tại"
    js = APP_JS.read_text(encoding="utf-8")

    assert "btnResetMemory: document.getElementById('btn-reset-memory')" in js
    assert "el.btnResetMemory.addEventListener('click', handleResetMemory)" in js


def test_app_js_handleResetMemory_calls_delete_api():
    """handleResetMemory phải gửi DELETE /api/memory kèm user_id và gọi updateMemoryStatus(0)."""
    assert APP_JS.exists()
    js = APP_JS.read_text(encoding="utf-8")

    assert "async function handleResetMemory()" in js
    assert "/api/memory?user_id=" in js
    assert "method: 'DELETE'" in js
    assert "updateMemoryStatus(0)" in js
    assert "Đã xóa bộ nhớ" in js


def test_app_js_displays_cache_hit_badge():
    """app.js phải render thẻ .badge-cache-hit với nội dung '⚡ Cache Hit' khi có cờ cache_hit: true."""
    assert APP_JS.exists()
    js = APP_JS.read_text(encoding="utf-8")

    # Kiểm tra kiểm tra cờ cache_hit
    assert "cache_hit === true" in js
    # Kiểm tra chèn class badge-cache-hit
    assert "badge-cache-hit" in js
    # Kiểm tra icon và chữ tiếng Việt
    assert "⚡ Cache Hit" in js
    assert "Phản hồi tức thì từ bộ đệm TTL Cache" in js


def test_app_js_fetchUserMemoryStatus_syncs_memory_badge():
    """fetchUserMemoryStatus phải gọi GET /api/memory và đồng bộ số facts vào UI."""
    assert APP_JS.exists()
    js = APP_JS.read_text(encoding="utf-8")

    assert "async function fetchUserMemoryStatus()" in js
    assert "getApiEndpoint(`/api/memory?user_id=" in js
    assert "updateMemoryStatus" in js


def test_frontend_static_serving_of_assets(client):
    """Máy chủ backend phục vụ đúng mã nguồn tĩnh của Frontend."""
    # Trang chủ
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "Reset Memory" in res_index.text

    # File JS
    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200
    assert "handleResetMemory" in res_js.text
    assert "⚡ Cache Hit" in res_js.text

    # File CSS
    res_css = client.get("/static/style.css")
    assert res_css.status_code == 200
    assert ".badge-cache-hit" in res_css.text
