from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


class CryptoError(Exception):
    pass


def _derive_dev_key(seed: str) -> str:
    digest = hashlib.sha256(seed.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8')


def _load_fernet(key: str | None = None) -> Fernet:
    raw = key or os.environ.get('INFRA_ENCRYPTION_KEY', '')
    if not raw:
        # Stable local-dev fallback from SESSION_SECRET so restarts can decrypt.
        seed = os.environ.get('SESSION_SECRET', 'creanova-local-dev')
        raw = _derive_dev_key(f'infra:{seed}')
    try:
        return Fernet(raw.encode('utf-8') if isinstance(raw, str) else raw)
    except Exception as exc:
        raise CryptoError(
            'INFRA_ENCRYPTION_KEY must be a valid Fernet key '
            "(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
        ) from exc


def encrypt_text(
    plaintext: str, *, key: str | None = None, key_id: str = 'default'
) -> tuple[str, str]:
    token = _load_fernet(key).encrypt(plaintext.encode('utf-8')).decode('utf-8')
    return token, key_id


def decrypt_text(ciphertext: str, *, key: str | None = None) -> str:
    try:
        return _load_fernet(key).decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise CryptoError('credential unreadable — encryption key mismatch') from exc
