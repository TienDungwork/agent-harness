"""Keyword retrieval cho task cards YAML VMS (duy style)."""
from __future__ import annotations
import re
from typing import Any
from src.domain.knowledge.loader import load_published_cards
_STOP = {'có', 'bao', 'nhiêu', 'nào', 'trong', 'của', 'và', 'the', 'a', 'an', 'là', 'đang', 'cho', 'tôi', 'những', 'các', 'một', 'làm', 'sao', 'thế', 'nào', 'cách', 'hướng', 'dẫn', 'giúp', 'gì', 'ở', 'đâu', 'được', 'không', 'với', 'hôm', 'nay', 'ngày', 'thời', 'tiết', 'mưa', 'nắng'}
_PHRASES = sorted(['thêm camera', 'thêm một camera mới', 'thêm camera mới', 'thêm một camera', 'quy trình thêm camera', 'xóa camera', 'sửa camera', 'chỉnh sửa camera', 'trạng thái camera', 'trực tuyến', 'ngoại tuyến', 'bảo trì', 'quản lý camera', 'đăng nhập', 'đăng xuất', 'xem live', 'trực tiếp', 'playback', 'phát lại', 'xem lại camera', 'xem lại', 'biển số', 'khuôn mặt', 'chấm công', 'không xem được live', 'camera bị đen', 'đổi mật khẩu', 'đặt lại mật khẩu', 'quên mật khẩu', 'xe máy', 'ô tô', 'làm thế nào để xem', 'vẽ vùng giám sát', 'lịch sử nhận diện'], key=len, reverse=True)

def _word_tokens(text: str) -> list[str]:
    """Tách từ đơn tiếng Việt (>= 2 ký tự, bỏ stop words)."""
    return [t for t in re.findall('\\w+', text.lower(), flags=re.UNICODE) if len(t) >= 2 and t not in _STOP]

def _tokens(text: str) -> list[str]:
    """Trích xuất cả cụm từ ưu tiên (_PHRASES) và từ đơn."""
    lowered = (text or '').lower()
    spans: list[tuple[int, int, str]] = []
    for phrase in _PHRASES:
        start = 0
        while True:
            i = lowered.find(phrase, start)
            if i < 0:
                break
            spans.append((i, i + len(phrase), phrase))
            start = i + len(phrase)
    spans.sort(key=lambda s: (-(s[1] - s[0]), s[0]))
    chosen: list[tuple[int, int, str]] = []
    occupied = [False] * (len(lowered) + 1)
    for a, b, phrase in spans:
        if any(occupied[a:b]):
            continue
        for i in range(a, b):
            occupied[i] = True
        chosen.append((a, b, phrase))
    chosen.sort(key=lambda s: s[0])
    tokens: list[str] = []
    cursor = 0
    for a, b, phrase in chosen:
        tokens.extend(_word_tokens(lowered[cursor:a]))
        tokens.append(phrase)
        cursor = b
    tokens.extend(_word_tokens(lowered[cursor:]))
    return tokens

def retrieve_docs(question: str, *, limit: int=3, min_score: int=4, prefer_type: str | None=None) -> list[dict[str, Any]]:
    """Tìm top-k cards phù hợp nhất với câu hỏi dựa vào alias, title, tag, phrase."""
    q = (question or '').lower()
    tokens = _tokens(q)
    scored: list[tuple[int, dict[str, Any]]] = []
    for card in load_published_cards():
        type_penalty = 3 if prefer_type and str((card['type'] if 'type' in card else None) or '') != prefer_type else 0
        aliases = [str(a).lower() for a in (card['aliases'] if 'aliases' in card else None) or []]
        tags = [str(t).lower() for t in (card['tags'] if 'tags' in card else None) or []]
        menu_path_str = ' '.join((str(m) for m in (card['menu_path'] if 'menu_path' in card else None) or [])).lower()
        route_str = str((card['route'] if 'route' in card else None) or '').lower()
        hay = ' '.join([str((card['id'] if 'id' in card else None) or ''), str((card['title'] if 'title' in card else None) or ''), str((card['intent'] if 'intent' in card else None) or ''), str((card['summary'] if 'summary' in card else None) or ''), str((card['module'] if 'module' in card else None) or ''), menu_path_str, route_str, ' '.join(aliases), ' '.join(tags)]).lower()
        score = 0
        for alias in aliases:
            a = alias.strip()
            if not a:
                continue
            if a in q:
                score += 14 if ' ' in a or len(a) >= 6 else 10
        title = str((card['title'] if 'title' in card else None) or '').lower()
        if title and title in q:
            score += 12
        for token in tokens:
            if token in aliases:
                score += 8
            elif any((token in a.split() for a in aliases)):
                score += 3
            elif token in tags:
                score += 4
            elif token in hay:
                score += 1
        cid = str((card['id'] if 'id' in card else None) or '')
        if any((k in q for k in ('trạng thái', 'trực tuyến', 'ngoại tuyến', 'bảo trì'))):
            if cid == 'aioc.camera_status':
                score += 30
            elif cid == 'devices.edit_camera':
                score += 25
        if 'thêm' in q and 'camera' in q:
            if 'aioc' in q and cid == 'aioc.add_camera':
                score += 30
            elif cid == 'devices.add_camera':
                score += 25
        if any((k in q for k in ('sơ đồ', 'quy trình'))) and 'camera' in q and (cid == 'aioc.diagram_add_camera'):
            score += 35
        if any((k in q for k in ('sơ đồ', 'quy trình'))) and ('đăng nhập' in q or 'mở' in q) and (cid == 'aioc.diagram_login_devices'):
            score += 35
        if any((k in q for k in ('khác gì so với', 'phân biệt'))) and cid == 'aioc.vms_vs_devices':
            score += 35
        if any((k in q for k in ('quản lý camera', 'devices', 'aioc'))) and ('quản lý camera' in menu_path_str or 'devices' in route_str):
            score += 20
        score -= type_penalty
        if score >= min_score:
            scored.append((score, card))
    scored.sort(key=lambda x: (-x[0], str((x[1]['id'] if 'id' in x[1] else None) or '')))
    return [c for _, c in scored[:limit]]

def card_excerpt_for_llm(card: dict[str, Any]) -> dict[str, Any]:
    """Rút gọn thông tin card cần thiết để đưa vào prompt cho LLM."""
    steps = []
    for step in (card['steps'] if 'steps' in card else None) or []:
        if not isinstance(step, dict):
            continue
        item: dict[str, Any] = {'order': step['order'] if 'order' in step else None, 'say': step['say'] if 'say' in step else None}
        ui = (step['ui'] if 'ui' in step else None) or {}
        if isinstance(ui, dict) and (ui['label'] if 'label' in ui else None):
            item['ui_label'] = ui['label'] if 'label' in ui else None
        steps.append(item)
    checks = []
    for chk in (card['checks'] if 'checks' in card else None) or []:
        if not isinstance(chk, dict):
            continue
        checks.append({'order': chk['order'] if 'order' in chk else None, 'if': chk['if'] if 'if' in chk else None, 'then': chk['then'] if 'then' in chk else None, 'stop_when': chk['stop_when'] if 'stop_when' in chk else None})
    return {'id': card['id'] if 'id' in card else None, 'type': card['type'] if 'type' in card else None, 'title': card['title'] if 'title' in card else None, 'module': card['module'] if 'module' in card else None, 'route': card['route'] if 'route' in card else None, 'menu_path': card['menu_path'] if 'menu_path' in card else None, 'preconditions': card['preconditions'] if 'preconditions' in card else None, 'summary': card['summary'] if 'summary' in card else None, 'symptoms': card['symptoms'] if 'symptoms' in card else None, 'steps': steps or None, 'checks': checks or None}
