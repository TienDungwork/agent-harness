from __future__ import annotations

import logging
import sys
import time
from typing import Any

import clickhouse_connect
import psycopg
from clickhouse_connect.driver.client import Client
from config import Settings
from psycopg.rows import dict_row
from sources import AI_COLUMNS, SOURCES, Source, map_row_safe

log = logging.getLogger('vms-sync')

RETRY_BACKOFF = (5, 15, 45)

log = logging.getLogger('vms-sync')

RETRY_BACKOFF = (5, 15, 45)


def wait_clickhouse(settings: Settings) -> Client:
    deadline = time.monotonic() + settings.ch_ready_timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client = clickhouse_connect.get_client(
                host=_ch_host(settings.ch_url),
                port=_ch_port(settings.ch_url),
                username=settings.ch_user,
                password=settings.ch_password,
                database=settings.ch_database,
            )
            client.query('SELECT 1')
            return client
        except Exception as exc:
            last_error = exc
            log.warning('ClickHouse not ready: %s', exc)
            time.sleep(10)
    raise SystemExit(
        f'ClickHouse not ready after {settings.ch_ready_timeout_seconds}s: {last_error}'
    )


def _ch_host(url: str) -> str:
    stripped = url.removeprefix('http://').removeprefix('https://')
    return stripped.split(':')[0].split('/')[0]


def _ch_port(url: str) -> int:
    stripped = url.removeprefix('http://').removeprefix('https://')
    hostport = stripped.split('/')[0]
    if ':' in hostport:
        return int(hostport.split(':')[1])
    return 8123


def read_watermark(ch: Client, src: Source) -> int:
    result = ch.query(
        'SELECT max(src_id) FROM vms.ai_events WHERE src_db = {db:String} AND src_table = {tbl:String}',
        parameters={'db': src.db, 'tbl': src.table},
    )
    value = result.result_rows[0][0] if result.result_rows else None
    if value is None:
        return 0
    return int(value)


def probe_sources(settings: Settings) -> tuple[Source, ...]:
    """Drop sources the role cannot SELECT (extra DBs until GRANT). Other errors stay enabled."""
    enabled: list[Source] = []
    for src in SOURCES:
        try:
            fetch_batch(settings, src, 2**62)
            enabled.append(src)
            log.info('source enabled %s.%s', src.db, src.table)
        except psycopg.errors.InsufficientPrivilege:
            log.warning('skip %s.%s: no SELECT grant', src.db, src.table)
        except Exception as exc:
            log.warning(
                'probe %s.%s failed (%s); keep retrying each round',
                src.db,
                src.table,
                exc,
            )
            enabled.append(src)
    if not enabled:
        raise SystemExit('no Postgres sources enabled')
    return tuple(enabled)


def fetch_batch(
    settings: Settings, src: Source, watermark: int
) -> list[dict[str, Any]]:
    conninfo = (
        f'host={settings.pg_host} port={settings.pg_port} '
        f'dbname={src.db} user={settings.pg_user} password={settings.pg_password}'
    )
    with psycopg.connect(conninfo, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                src.select_sql, (watermark, settings.lag_seconds, settings.batch_size)
            )
            return list(cur.fetchall())


def insert_events(ch: Client, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    data = [[row[col] for col in AI_COLUMNS] for row in rows]
    ch.insert('vms.ai_events', data, column_names=list(AI_COLUMNS))


def insert_with_retry(
    ch: Client, rows: list[dict[str, Any]], sleep_fn=time.sleep
) -> None:
    last_error: Exception | None = None
    for delay in (0, *RETRY_BACKOFF):
        if delay:
            sleep_fn(delay)
        try:
            insert_events(ch, rows)
            return
        except Exception as exc:
            last_error = exc
            log.warning('ClickHouse insert failed: %s', exc)
    raise last_error  # type: ignore[misc]


def write_sync_state(
    ch: Client,
    src: Source,
    *,
    last_id: int,
    rows_copied: int,
    ok: bool,
    error: str = '',
) -> None:
    ch.insert(
        'vms.sync_state',
        [[src.db, src.table, last_id, rows_copied, 1 if ok else 0, error[:2000]]],
        column_names=['src_db', 'src_table', 'last_id', 'rows_copied', 'ok', 'error'],
    )


def run_source(settings: Settings, ch: Client, src: Source, sleep_fn=time.sleep) -> int:
    """Copy one batch. Returns number of rows inserted. Does not advance watermark on CH failure."""
    watermark = read_watermark(ch, src)
    try:
        raw = fetch_batch(settings, src, watermark)
    except Exception as exc:
        log.exception('Postgres fetch failed for %s.%s', src.db, src.table)
        try:
            write_sync_state(
                ch, src, last_id=watermark, rows_copied=0, ok=False, error=str(exc)
            )
        except Exception:
            log.exception('Could not write sync_state after Postgres error')
        return 0
    mapped = [
        map_row_safe(src.mapper, dict(row), src_db=src.db, src_table=src.table)
        for row in raw
    ]
    if not mapped:
        write_sync_state(ch, src, last_id=watermark, rows_copied=0, ok=True)
        return 0
    max_id = max(int(r['src_id']) for r in mapped)
    try:
        insert_with_retry(ch, mapped, sleep_fn=sleep_fn)
    except Exception as exc:
        log.exception(
            'ClickHouse insert failed for %s.%s; watermark stays %s',
            src.db,
            src.table,
            watermark,
        )
        try:
            write_sync_state(
                ch, src, last_id=watermark, rows_copied=0, ok=False, error=str(exc)
            )
        except Exception:
            log.exception('Could not write sync_state after ClickHouse error')
        return 0
    write_sync_state(ch, src, last_id=max_id, rows_copied=len(mapped), ok=True)
    log.info('%s.%s copied %s rows up to id=%s', src.db, src.table, len(mapped), max_id)
    return len(mapped)


def run_round(
    settings: Settings, ch: Client, sources: tuple[Source, ...] = SOURCES
) -> bool:
    """Return True if any source filled a full batch (keep going without sleep)."""
    full = False
    for src in sources:
        copied = run_source(settings, ch, src)
        if copied >= settings.batch_size:
            full = True
    return full


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        stream=sys.stdout,
    )
    settings = Settings()
    ch = wait_clickhouse(settings)
    sources = probe_sources(settings)
    log.info(
        'vms-sync started, poll=%ss batch=%s lag=%ss sources=%s',
        settings.poll_seconds,
        settings.batch_size,
        settings.lag_seconds,
        ','.join(f'{s.db}.{s.table}' for s in sources),
    )
    while True:
        try:
            keep_going = run_round(settings, ch, sources)
        except Exception:
            log.exception('Unexpected error in sync round')
            keep_going = False
        if keep_going:
            continue
        time.sleep(settings.poll_seconds)


if __name__ == '__main__':
    main()
