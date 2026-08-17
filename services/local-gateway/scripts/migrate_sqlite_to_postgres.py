#!/usr/bin/env python3
"""Copy Milestone 1/2 SQLite data into PostgreSQL (idempotent)."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storage.models import (  # noqa: E402
    CreditAccount,
    UsageLedger,
    User,
    UserConversation,
    UserSettingsBlob,
    init_db,
)


def _copy(src_url: str, dst_url: str, *, apply: bool) -> None:
    src_engine = create_engine(src_url)
    SrcSession = sessionmaker(bind=src_engine)
    src = SrcSession()

    init_db(dst_url)
    from storage.models import SessionLocal

    assert SessionLocal is not None
    dst = SessionLocal()

    users = src.execute(text('SELECT * FROM users')).mappings().all()
    print(f'users: {len(users)}')
    if apply:
        for row in users:
            if dst.query(User).filter(User.id == row['id']).one_or_none():
                continue
            dst.add(
                User(
                    id=row['id'],
                    keycloak_sub=row.get('keycloak_sub'),
                    username=row['username'],
                    email=row.get('email'),
                    password_hash=row.get('password_hash'),
                    is_admin=bool(row.get('is_admin')),
                    is_active=bool(row.get('is_active', True)),
                )
            )
        dst.commit()

    accounts = src.execute(text('SELECT * FROM credit_accounts')).mappings().all()
    print(f'credit_accounts: {len(accounts)}')
    if apply:
        for row in accounts:
            if (
                dst.query(CreditAccount)
                .filter(CreditAccount.user_id == row['user_id'])
                .one_or_none()
            ):
                continue
            dst.add(
                CreditAccount(
                    user_id=row['user_id'],
                    balance=Decimal(str(round(float(row['balance']), 4))),
                    credit_limit=Decimal(str(round(float(row['credit_limit']), 4))),
                )
            )
        dst.commit()

    ledger = src.execute(text('SELECT * FROM usage_ledger')).mappings().all()
    print(f'usage_ledger: {len(ledger)}')
    if apply:
        for row in ledger:
            dst.add(
                UsageLedger(
                    user_id=row['user_id'],
                    conversation_id=row.get('conversation_id'),
                    run_id=row.get('run_id'),
                    usage_type=row.get('usage_type') or 'llm_run',
                    units=Decimal(str(round(float(row.get('units') or 0), 4))),
                    cost=Decimal(str(round(float(row.get('cost') or 0), 4))),
                )
            )
        dst.commit()

    convs = src.execute(text('SELECT * FROM user_conversations')).mappings().all()
    print(f'user_conversations: {len(convs)}')
    if apply:
        for row in convs:
            if (
                dst.query(UserConversation)
                .filter(UserConversation.conversation_id == row['conversation_id'])
                .one_or_none()
            ):
                continue
            dst.add(
                UserConversation(
                    conversation_id=row['conversation_id'],
                    user_id=row['user_id'],
                    title=row.get('title'),
                    status='active',
                    source='import',
                )
            )
        dst.commit()

    try:
        blobs = src.execute(text('SELECT * FROM user_settings_blobs')).mappings().all()
    except Exception:
        blobs = []
    print(f'user_settings_blobs: {len(blobs)}')
    if apply:
        for row in blobs:
            if (
                dst.query(UserSettingsBlob)
                .filter(
                    UserSettingsBlob.user_id == row['user_id'],
                    UserSettingsBlob.kind == row['kind'],
                )
                .one_or_none()
            ):
                continue
            payload = row.get('payload') or '{}'
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    print(f'skip bad blob {row["user_id"]}/{row["kind"]}')
                    continue
            dst.add(
                UserSettingsBlob(
                    user_id=row['user_id'], kind=row['kind'], payload=payload
                )
            )
        dst.commit()

    if apply:
        print('Applied.')
        print(
            f'dst users={dst.query(User).count()} credits_sum={dst.execute(text("SELECT COALESCE(SUM(balance),0) FROM credit_accounts")).scalar()}'
        )
    else:
        print('Dry-run only. Re-run with --apply to write.')

    src.close()
    dst.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--sqlite', required=True, help='sqlite:////path/to.db or path')
    p.add_argument(
        '--postgres',
        default='postgresql+psycopg://creanova:creanova_dev_change_me@127.0.0.1:54288/creanova',
    )
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    sqlite = args.sqlite
    if not sqlite.startswith('sqlite:'):
        sqlite = f'sqlite:///{sqlite}'
    _copy(sqlite, args.postgres, apply=args.apply)


if __name__ == '__main__':
    main()
