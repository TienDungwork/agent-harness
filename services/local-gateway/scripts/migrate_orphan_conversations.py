#!/usr/bin/env python3
"""Claim orphan agent-server conversations for a bootstrap admin user.

Usage (from services/local-gateway):

  AGENT_SERVER_URL=http://127.0.0.1:18000 \\
  AGENT_SERVER_API_KEY=... \\
  DATABASE_URL=sqlite:////path/to/local-gateway.db \\
  uv run python scripts/migrate_orphan_conversations.py --username admin

Dry-run is the default; pass --apply to write ownership rows.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

# Allow running as `python scripts/...` from local-gateway root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.models import SessionLocal, User, UserConversation, init_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default='admin')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument(
        '--agent-server-url',
        default=os.getenv('AGENT_SERVER_URL', 'http://127.0.0.1:18000'),
    )
    parser.add_argument(
        '--api-key',
        default=os.getenv('AGENT_SERVER_API_KEY', ''),
    )
    parser.add_argument(
        '--database-url',
        default=os.getenv('DATABASE_URL', 'sqlite:////tmp/creanova-local-gateway.db'),
    )
    args = parser.parse_args()

    init_db(args.database_url)
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).one_or_none()
        if user is None:
            print(f"User '{args.username}' not found in gateway DB. Login once first.")
            return 1

        headers = {}
        if args.api_key:
            headers['X-Session-API-Key'] = args.api_key
        url = f'{args.agent_server_url.rstrip("/")}/api/conversations/search?limit=100'
        resp = httpx.get(url, headers=headers, timeout=60.0)
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get('items') if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            print('Unexpected conversations response')
            return 1

        claimed = {row[0] for row in db.query(UserConversation.conversation_id).all()}
        orphans = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cid = str(item.get('id') or item.get('conversation_id') or '')
            if cid and cid not in claimed:
                orphans.append(cid)

        print(f'Found {len(orphans)} orphan conversation(s) for user={args.username}')
        for cid in orphans:
            print(f'  - {cid}')
            if args.apply:
                db.add(
                    UserConversation(
                        conversation_id=cid,
                        user_id=user.id,
                        title=None,
                    )
                )
        if args.apply and orphans:
            db.commit()
            print('Applied.')
        else:
            print('Dry-run only. Re-run with --apply to write ownership.')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
