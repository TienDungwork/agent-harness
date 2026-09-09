from __future__ import annotations

from unittest.mock import MagicMock

import psycopg
from main import insert_with_retry, probe_sources, run_source
from sources import SOURCES


def test_insert_retry_does_not_succeed_until_last(monkeypatch):
    calls = {'n': 0}

    def flaky(_ch, _rows):
        calls['n'] += 1
        if calls['n'] < 3:
            raise RuntimeError('timeout')

    monkeypatch.setattr('main.insert_events', flaky)
    sleeps: list[int] = []
    insert_with_retry(MagicMock(), [{'x': 1}], sleep_fn=sleeps.append)
    assert calls['n'] == 3
    assert sleeps == [5, 15]


def test_run_source_keeps_watermark_when_insert_fails(monkeypatch):
    src = SOURCES[0]
    ch = MagicMock()
    settings = MagicMock(
        lag_seconds=30,
        batch_size=20000,
        pg_host='h',
        pg_port=1,
        pg_user='u',
        pg_password='p',
    )
    monkeypatch.setattr('main.read_watermark', lambda _ch, _src: 100)
    monkeypatch.setattr(
        'main.fetch_batch',
        lambda *_a, **_k: [
            {'id': 101, 'direction': 'IN', 'event_time': None, 'created_at': None}
        ],
    )

    def fail_insert(*_a, **_k):
        raise RuntimeError('ch down')

    monkeypatch.setattr('main.insert_with_retry', fail_insert)
    states: list[tuple] = []

    def capture(_ch, _src, **kwargs):
        states.append(kwargs)

    monkeypatch.setattr('main.write_sync_state', capture)
    copied = run_source(settings, ch, src, sleep_fn=lambda _d: None)
    assert copied == 0
    assert states[-1]['ok'] is False
    assert states[-1]['last_id'] == 100


def test_probe_skips_insufficient_privilege(monkeypatch):
    settings = MagicMock()

    def fetch(_settings, src, _watermark):
        if src.db == 'footfall':
            raise psycopg.errors.InsufficientPrivilege('denied')
        return []

    monkeypatch.setattr('main.fetch_batch', fetch)
    enabled = probe_sources(settings)
    names = {f'{s.db}.{s.table}' for s in enabled}
    assert 'its.plate_event' in names
    assert 'footfall.footfall_event' not in names
