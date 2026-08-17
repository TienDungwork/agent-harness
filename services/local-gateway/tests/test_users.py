from __future__ import annotations

import storage.models as models
from storage.users import (
    claim_conversation,
    list_user_conversation_ids,
    upsert_user_from_claims,
)


def test_conversation_ownership(tmp_path):
    db_url = f'sqlite:///{tmp_path}/gw.db'
    models.init_db(db_url)
    assert models.SessionLocal is not None
    db = models.SessionLocal()
    try:
        a = upsert_user_from_claims(
            db,
            keycloak_sub='sub-a',
            username='alice',
            email='a@x',
            is_admin=False,
        )
        b = upsert_user_from_claims(
            db,
            keycloak_sub='sub-b',
            username='bob',
            email='b@x',
            is_admin=False,
        )
        claim_conversation(db, a.id, '11111111-1111-1111-1111-111111111111')
        assert '11111111-1111-1111-1111-111111111111' in list_user_conversation_ids(
            db, a.id
        )
        assert '11111111-1111-1111-1111-111111111111' not in list_user_conversation_ids(
            db, b.id
        )
        try:
            claim_conversation(db, b.id, '11111111-1111-1111-1111-111111111111')
            raise AssertionError('expected PermissionError')
        except PermissionError:
            pass
        assert db.query(models.UserConversation).count() == 1
    finally:
        db.close()
