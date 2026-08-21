from __future__ import annotations

from types import SimpleNamespace

from infra.pins import rank_pins


def test_rank_pins_exact_container_wins():
    pins = [
        SimpleNamespace(
            id='1',
            user_id='u1',
            host='192.168.1.250',
            container_name='ollama',
            container_id='abc',
            image='ollama/ollama',
            tags=['llm'],
            note=None,
            server_id=None,
        ),
        SimpleNamespace(
            id='2',
            user_id='u1',
            host='192.168.1.250',
            container_name='nginx',
            container_id=None,
            image=None,
            tags=[],
            note=None,
            server_id=None,
        ),
    ]
    ranked = rank_pins('ollama', pins)
    assert ranked[0].pin_id == '1'
    assert ranked[0].match == 'container_exact'
    assert ranked[0].score == 100


def test_rank_pins_host_and_tag():
    pins = [
        SimpleNamespace(
            id='a',
            user_id='u',
            host='lab-gpu',
            container_name='triton',
            container_id=None,
            image='nvcr.io/triton',
            tags=['gpu', 'infer'],
            note='prod',
            server_id=None,
        )
    ]
    by_host = rank_pins('lab-gpu', pins)
    assert by_host[0].match == 'host_exact'
    by_tag = rank_pins('infer', pins)
    assert by_tag[0].match == 'tag_exact'


def test_rank_pins_empty_query():
    assert rank_pins('  ', []) == []
