from __future__ import annotations

from dataclasses import dataclass

import httpx
from config import Settings


@dataclass
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str


@dataclass
class UserInfo:
    sub: str
    username: str
    email: str | None
    roles: list[str]


class KeycloakClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def password_grant(self, username: str, password: str) -> TokenResponse:
        data = {
            'grant_type': 'password',
            'client_id': self.settings.keycloak_client_id,
            'client_secret': self.settings.keycloak_client_secret,
            'username': username,
            'password': password,
            'scope': 'openid profile email',
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.settings.keycloak_token_url, data=data)
        if resp.status_code >= 400:
            detail = resp.text
            raise PermissionError(f'Keycloak login failed: {detail}')
        body = resp.json()
        return TokenResponse(
            access_token=body['access_token'],
            refresh_token=body.get('refresh_token'),
            expires_in=int(body.get('expires_in', 3600)),
            token_type=body.get('token_type', 'Bearer'),
        )

    async def userinfo(self, access_token: str) -> UserInfo:
        headers = {'Authorization': f'Bearer {access_token}'}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self.settings.keycloak_userinfo_url, headers=headers
            )
        if resp.status_code >= 400:
            raise PermissionError('Failed to fetch userinfo')
        body = resp.json()
        # Prefer realm roles from token introspection via userinfo custom claims if present
        roles = (
            body.get('realm_access', {}).get('roles')
            if isinstance(body.get('realm_access'), dict)
            else []
        )
        if not roles:
            roles = body.get('roles') or []
        username = (
            body.get('preferred_username')
            or body.get('username')
            or body.get('email')
            or body['sub']
        )
        return UserInfo(
            sub=body['sub'],
            username=username,
            email=body.get('email'),
            roles=list(roles),
        )

    async def decode_roles_from_access_token(self, access_token: str) -> list[str]:
        """Best-effort decode of realm roles without verifying signature locally.

        Keycloak password-grant tokens are validated by calling userinfo; roles are
        often only in the JWT. We decode the payload (unverified) for role checks.
        """
        try:
            from jose import jwt

            claims = jwt.get_unverified_claims(access_token)
            realm = claims.get('realm_access') or {}
            return list(realm.get('roles') or [])
        except Exception:
            return []
