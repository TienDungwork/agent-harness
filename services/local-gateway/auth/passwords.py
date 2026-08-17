from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        _ITERATIONS,
    ).hex()
    return f'pbkdf2_sha256${_ITERATIONS}${salt}${digest}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters_s, salt, digest = encoded.split('$', 3)
        if algo != 'pbkdf2_sha256':
            return False
        iters = int(iters_s)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iters,
    ).hex()
    return hmac.compare_digest(candidate, digest)
