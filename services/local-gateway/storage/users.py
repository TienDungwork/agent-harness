from __future__ import annotations

import uuid
from dataclasses import dataclass

from auth.passwords import hash_password, verify_password
from sqlalchemy.orm import Session

from storage.models import CreditAccount, User, UserConversation


@dataclass
class AuthUser:
    id: str
    username: str
    email: str | None
    is_admin: bool
    credit_balance: float


def upsert_user_from_claims(
    db: Session,
    *,
    keycloak_sub: str,
    username: str,
    email: str | None,
    is_admin: bool,
    initial_credits: float = 100.0,
) -> User:
    user = db.query(User).filter(User.keycloak_sub == keycloak_sub).one_or_none()
    if user is None:
        user = User(
            id=str(uuid.uuid4()),
            keycloak_sub=keycloak_sub,
            username=username,
            email=email,
            is_admin=is_admin,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(
            CreditAccount(
                user_id=user.id,
                balance=initial_credits,
                credit_limit=initial_credits,
            )
        )
    else:
        user.username = username
        user.email = email
        user.is_admin = is_admin
        if not user.is_active:
            raise PermissionError('User is disabled')
    db.commit()
    db.refresh(user)
    return user


def get_or_create_local_user(
    db: Session,
    *,
    username: str,
    password: str,
    email: str | None = None,
    is_admin: bool = False,
    initial_credits: float = 100.0,
) -> User:
    existing = db.query(User).filter(User.username == username).one_or_none()
    if existing is not None:
        existing.password_hash = hash_password(password)
        if email is not None:
            existing.email = email
        existing.is_admin = is_admin
        db.commit()
        db.refresh(existing)
        return existing

    user = User(
        id=str(uuid.uuid4()),
        keycloak_sub=f'local:{username}',
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_admin=is_admin,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        CreditAccount(
            user_id=user.id,
            balance=initial_credits,
            credit_limit=initial_credits,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def authenticate_local(db: Session, *, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).one_or_none()
    if user is None or not user.password_hash:
        raise PermissionError('Invalid username or password')
    if not user.is_active:
        raise PermissionError('User is disabled')
    if not verify_password(password, user.password_hash):
        raise PermissionError('Invalid username or password')
    return user


def create_local_user(
    db: Session,
    *,
    username: str,
    password: str,
    email: str | None = None,
    is_admin: bool = False,
    initial_credits: float = 100.0,
) -> User:
    if db.query(User).filter(User.username == username).one_or_none():
        raise ValueError('Username already exists')
    return get_or_create_local_user(
        db,
        username=username,
        password=password,
        email=email,
        is_admin=is_admin,
        initial_credits=initial_credits,
    )


def to_auth_user(user: User) -> AuthUser:
    balance = float(user.credit_account.balance) if user.credit_account else 0.0
    return AuthUser(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        credit_balance=balance,
    )


def claim_conversation(
    db: Session, user_id: str, conversation_id: str, title: str | None = None
) -> None:
    existing = (
        db.query(UserConversation)
        .filter(UserConversation.conversation_id == conversation_id)
        .one_or_none()
    )
    if existing is None:
        db.add(
            UserConversation(
                conversation_id=conversation_id,
                user_id=user_id,
                title=title,
            )
        )
        db.commit()
        return
    if existing.user_id != user_id:
        raise PermissionError('Conversation belongs to another user')


def list_user_conversation_ids(db: Session, user_id: str) -> set[str]:
    rows = db.query(UserConversation.conversation_id).filter(
        UserConversation.user_id == user_id
    )
    return {row[0] for row in rows}


def seed_local_users(db: Session) -> None:
    """Bootstrap admin/demo when AUTH_BACKEND=local (no Docker/Keycloak)."""
    seeds = [
        ('admin', 'admin123', 'admin@creanova.local', True),
        ('demo', 'demo123', 'demo@creanova.local', False),
    ]
    for username, password, email, is_admin in seeds:
        existing = db.query(User).filter(User.username == username).one_or_none()
        if existing is None:
            get_or_create_local_user(
                db,
                username=username,
                password=password,
                email=email,
                is_admin=is_admin,
                initial_credits=100.0,
            )
        elif not existing.password_hash:
            existing.password_hash = hash_password(password)
            existing.is_admin = is_admin or existing.is_admin
            db.commit()
