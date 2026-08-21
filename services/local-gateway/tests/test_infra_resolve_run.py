from __future__ import annotations

from types import SimpleNamespace

from infra.destructive import destructive_reason, looks_destructive
from infra.resolve import rank_servers


def test_rank_servers_exact_hostname_wins():
    servers = [
        SimpleNamespace(
            id='1',
            name='lab-gpu',
            hostname='192.168.1.250',
            port=22,
            username='root',
            tags=['gpu'],
        ),
        SimpleNamespace(
            id='2',
            name='250-backup',
            hostname='192.168.1.251',
            port=22,
            username='ubuntu',
            tags=[],
        ),
    ]
    ranked = rank_servers('192.168.1.250', servers)
    assert ranked[0].server_id == '1'
    assert ranked[0].match == 'hostname_exact'
    assert ranked[0].score == 100


def test_rank_servers_name_and_tag():
    servers = [
        SimpleNamespace(
            id='a',
            name='nemotron',
            hostname='10.0.0.5',
            port=22,
            username='atin',
            tags=['llm', 'ollama'],
        )
    ]
    by_name = rank_servers('nemotron', servers)
    assert by_name[0].match == 'name_exact'
    by_tag = rank_servers('ollama', servers)
    assert by_tag[0].match == 'tag_exact'


def test_rank_servers_empty_query():
    assert rank_servers('  ', []) == []


def test_destructive_rm_requires_confirm():
    assert looks_destructive('rm -rf /tmp/x')
    assert looks_destructive('echo hi; rm file')
    assert looks_destructive('find /data -name "*.log" -delete')
    assert looks_destructive('git clean -fd')
    assert not looks_destructive('ls -la /tmp')
    assert not looks_destructive('systemctl status nginx')
    assert destructive_reason('rm -rf /') is not None
    assert destructive_reason('uptime') is None
