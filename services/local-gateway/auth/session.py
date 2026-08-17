from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from config import Settings
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


@dataclass
class SessionPayload:
    user_id: str
    username: str
    is_admin: bool
    access_token: str
    refresh_token: str | None
    issued_at: int


class SessionManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._serializer = URLSafeTimedSerializer(
            settings.session_secret, salt='creanova-local-session'
        )

    def issue(self, payload: SessionPayload) -> str:
        return self._serializer.dumps(
            {
                'user_id': payload.user_id,
                'username': payload.username,
                'is_admin': payload.is_admin,
                'access_token': payload.access_token,
                'refresh_token': payload.refresh_token,
                'issued_at': payload.issued_at,
                'nonce': secrets.token_hex(8),
            }
        )

    def load(self, token: str) -> SessionPayload:
        try:
            data = self._serializer.loads(
                token, max_age=self.settings.session_ttl_seconds
            )
        except SignatureExpired as exc:
            raise PermissionError('Session expired') from exc
        except BadSignature as exc:
            raise PermissionError('Invalid session') from exc
        return SessionPayload(
            user_id=data['user_id'],
            username=data['username'],
            is_admin=bool(data.get('is_admin')),
            access_token=data['access_token'],
            refresh_token=data.get('refresh_token'),
            issued_at=int(data.get('issued_at', time.time())),
        )


def fingerprint_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
