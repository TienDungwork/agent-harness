from __future__ import annotations

from types import SimpleNamespace

from infra.destructive import (
    destructive_reason,
    looks_destructive,
    looks_like_sudo,
    sudo_blocked_reason,
)
from infra.resolve import (
    enrich_resolve_response,
    looks_like_ssh_connect_only,
    rank_servers,
)


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


def test_rank_servers_last_octet_beats_name_substring():
    """Chat shorthand '250' must pick 192.168.1.250, not a name that merely contains 250."""
    servers = [
        SimpleNamespace(
            id='1',
            name='lab-gpu',
            hostname='192.168.1.250',
            port=22,
            username='root',
            tags=[],
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
    ranked = rank_servers('250', servers)
    assert ranked[0].server_id == '1'
    assert ranked[0].match == 'hostname_last_octet'
    assert ranked[0].score == 70


def test_destructive_rm_requires_confirm():
    assert looks_destructive('rm -rf /tmp/x')
    assert looks_destructive('echo hi; rm file')
    assert looks_destructive('find /data -name "*.log" -delete')
    assert looks_destructive('git clean -fd')
    assert not looks_destructive('ls -la /tmp')
    assert not looks_destructive('systemctl status nginx')
    assert destructive_reason('rm -rf /') is not None
    assert destructive_reason('uptime') is None


def test_ssh_connect_only_intent():
    assert looks_like_ssh_connect_only('250')
    assert looks_like_ssh_connect_only('ssh vào 250')
    assert looks_like_ssh_connect_only('ssh vaof 250')
    assert not looks_like_ssh_connect_only('ls -la /home')


def test_enrich_resolve_adds_vi_reply_for_ssh_connect():
    items = [
        {
            'id': 'x',
            'hostname': '192.168.1.250',
            'username': 'atin',
        }
    ]
    extra = enrich_resolve_response('250', items)
    assert 'assistant_reply_vi' in extra
    assert '192.168.1.250' in extra['assistant_reply_vi']
    assert extra.get('do_not_call_infra_run') is True
    assert 'agent_instruction' in extra


def test_sudo_is_always_blocked():
    assert looks_like_sudo('sudo systemctl status nginx')
    assert looks_like_sudo('echo hi; sudo -n true')
    assert not looks_like_sudo('whoami')
    assert not looks_like_sudo('systemctl status nginx')
    reason = sudo_blocked_reason('sudo apt update')
    assert reason is not None
    assert 'sudo' in reason.lower() or 'Đã vào máy' in reason
    assert sudo_blocked_reason('uptime') is None
