from __future__ import annotations

from cryptography.fernet import Fernet
from infra.commands import CommandDenied, render_command, validate_unit
from infra.crypto import decrypt_text, encrypt_text
from infra.gpu import parse_nvidia_smi_csv


def test_crypto_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv('INFRA_ENCRYPTION_KEY', key)
    ct, kid = encrypt_text('secret-key-material')
    assert kid == 'default'
    assert decrypt_text(ct) == 'secret-key-material'
    assert 'secret' not in ct


def test_command_whitelist():
    assert 'echo ok' == render_command('echo_ok')
    assert 'nginx.service' in render_command('service_restart', unit='nginx.service')
    try:
        render_command('rm_rf')
        raise AssertionError('expected CommandDenied')
    except CommandDenied:
        pass
    try:
        validate_unit('nginx.service; rm -rf /')
        raise AssertionError('expected CommandDenied')
    except CommandDenied:
        pass


def test_gpu_parser():
    sample = (
        '0, GPU-aaa, NVIDIA RTX A6000, 49140, 12000, 45, 20, 62, 150.5\n'
        '1, GPU-bbb, NVIDIA RTX A6000, 49140, 8000, 10, 5, 55, 80.0\n'
    )
    gpus = parse_nvidia_smi_csv(sample)
    assert len(gpus) == 2
    assert gpus[0].gpu_index == 0
    assert gpus[0].mem_used_mb == 12000
    assert gpus[1].util_gpu_pct == 10
