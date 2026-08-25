from __future__ import annotations

import pytest
from infra.container_lifecycle import (
    ContainerLifecycleError,
    build_docker_lifecycle_command,
    pick_container_ref,
)


def test_prefer_container_id_over_name():
    assert (
        pick_container_ref(
            container_id='a' * 12,
            container_name='my-app',
        )
        == 'a' * 12
    )


def test_name_when_no_id():
    assert pick_container_ref(container_id=None, container_name='nginx') == 'nginx'


def test_invalid_id_rejected():
    with pytest.raises(ContainerLifecycleError):
        pick_container_ref(container_id='not-hex!', container_name='ok')


def test_build_start_quotes_name_with_space_like_chars():
    # Valid docker names cannot have spaces; hyphen/underscore ok.
    cmd = build_docker_lifecycle_command(
        'start',
        container_name='my_app.1',
    )
    assert cmd == 'docker start my_app.1'


def test_build_stop_uses_id():
    cid = 'abcdef012345'
    cmd = build_docker_lifecycle_command('STOP', container_id=cid, container_name='x')
    assert cmd == f'docker stop {cid}'


def test_unknown_action():
    with pytest.raises(ContainerLifecycleError):
        build_docker_lifecycle_command('pause', container_name='x')


def test_empty_refs():
    with pytest.raises(ContainerLifecycleError):
        build_docker_lifecycle_command('restart', container_id='', container_name='')
