from __future__ import annotations

import storage.models as models
from storage.credits import InsufficientCredits, charge_credits, refund_credits
from storage.users import upsert_user_from_claims


def test_charge_and_idempotent(tmp_path):
    models.init_db(f'sqlite:///{tmp_path}/c.db')
    db = models.SessionLocal()
    try:
        user = upsert_user_from_claims(
            db,
            keycloak_sub='sub-c',
            username='carol',
            email=None,
            is_admin=False,
            initial_credits=5.0,
        )
        r1 = charge_credits(
            db, user_id=user.id, cost=1.0, run_id='run-1', conversation_id='c1'
        )
        assert r1.balance == 4.0
        r2 = charge_credits(
            db, user_id=user.id, cost=1.0, run_id='run-1', conversation_id='c1'
        )
        assert r2.balance == 4.0
        assert r2.ledger_id == r1.ledger_id
        assert db.query(models.UsageLedger).count() == 1
    finally:
        db.close()


def test_insufficient_credits(tmp_path):
    models.init_db(f'sqlite:///{tmp_path}/c2.db')
    db = models.SessionLocal()
    try:
        user = upsert_user_from_claims(
            db,
            keycloak_sub='sub-d',
            username='dave',
            email=None,
            is_admin=False,
            initial_credits=0.5,
        )
        try:
            charge_credits(db, user_id=user.id, cost=1.0, run_id='run-x')
            raise AssertionError('expected InsufficientCredits')
        except InsufficientCredits as exc:
            assert exc.balance == 0.5
            assert exc.required == 1.0
    finally:
        db.close()


def test_refund(tmp_path):
    models.init_db(f'sqlite:///{tmp_path}/c3.db')
    db = models.SessionLocal()
    try:
        user = upsert_user_from_claims(
            db,
            keycloak_sub='sub-e',
            username='erin',
            email=None,
            is_admin=False,
            initial_credits=3.0,
        )
        charge_credits(db, user_id=user.id, cost=1.0, run_id='run-y')
        bal = refund_credits(db, user_id=user.id, amount=1.0, run_id='run-y')
        assert bal == 3.0
    finally:
        db.close()
