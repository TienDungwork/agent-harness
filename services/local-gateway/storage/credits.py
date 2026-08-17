from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from storage.models import CreditAccount, UsageLedger


@dataclass
class CreditChargeResult:
    balance: float
    cost: float
    ledger_id: int


class InsufficientCredits(Exception):
    def __init__(self, balance: float, required: float):
        self.balance = balance
        self.required = required
        super().__init__(
            f'Insufficient credits: balance={balance}, required={required}'
        )


def get_balance(db: Session, user_id: str) -> float:
    acct = (
        db.query(CreditAccount).filter(CreditAccount.user_id == user_id).one_or_none()
    )
    return float(acct.balance) if acct else 0.0


def assert_has_credits(db: Session, user_id: str, required: float) -> float:
    balance = get_balance(db, user_id)
    if balance < required:
        raise InsufficientCredits(balance=balance, required=required)
    return balance


def charge_credits(
    db: Session,
    *,
    user_id: str,
    cost: float,
    conversation_id: str | None = None,
    run_id: str | None = None,
    usage_type: str = 'llm_run',
    units: float = 1.0,
) -> CreditChargeResult:
    """Atomically deduct credits and append a ledger row.

    If ``run_id`` is set and a ledger row already exists for that run, this is a
    no-op (idempotent settlement). Unique index on (user_id, run_id) enforces
    this under concurrent Postgres writers.
    """
    if cost < 0:
        raise ValueError('cost must be >= 0')

    if run_id:
        existing = (
            db.query(UsageLedger)
            .filter(UsageLedger.user_id == user_id, UsageLedger.run_id == run_id)
            .filter(UsageLedger.usage_type != 'refund')
            .one_or_none()
        )
        if existing is not None:
            acct = (
                db.query(CreditAccount)
                .filter(CreditAccount.user_id == user_id)
                .one_or_none()
            )
            bal = float(acct.balance) if acct else 0.0
            return CreditChargeResult(
                balance=bal, cost=float(existing.cost), ledger_id=existing.id
            )

    acct = (
        db.query(CreditAccount)
        .filter(CreditAccount.user_id == user_id)
        .with_for_update()
        .one_or_none()
    )
    if acct is None:
        raise InsufficientCredits(balance=0.0, required=cost)
    if float(acct.balance) < cost:
        raise InsufficientCredits(balance=float(acct.balance), required=cost)

    acct.balance = Decimal(str(acct.balance)) - Decimal(str(cost))
    entry = UsageLedger(
        user_id=user_id,
        conversation_id=conversation_id,
        run_id=run_id,
        usage_type=usage_type,
        units=Decimal(str(units)),
        cost=Decimal(str(cost)),
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if run_id:
            existing = (
                db.query(UsageLedger)
                .filter(UsageLedger.user_id == user_id, UsageLedger.run_id == run_id)
                .filter(UsageLedger.usage_type != 'refund')
                .one_or_none()
            )
            if existing is not None:
                bal = get_balance(db, user_id)
                return CreditChargeResult(
                    balance=bal, cost=float(existing.cost), ledger_id=existing.id
                )
        raise
    db.refresh(acct)
    db.refresh(entry)
    return CreditChargeResult(
        balance=float(acct.balance), cost=cost, ledger_id=entry.id
    )


def refund_credits(
    db: Session,
    *,
    user_id: str,
    amount: float,
    conversation_id: str | None = None,
    run_id: str | None = None,
) -> float:
    """Credit the account back (e.g. upstream create/run failed after reserve)."""
    if amount <= 0:
        return get_balance(db, user_id)
    acct = (
        db.query(CreditAccount)
        .filter(CreditAccount.user_id == user_id)
        .with_for_update()
        .one_or_none()
    )
    if acct is None:
        return 0.0
    acct.balance = Decimal(str(acct.balance)) + Decimal(str(amount))
    db.add(
        UsageLedger(
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=f'refund:{run_id}' if run_id else None,
            usage_type='refund',
            units=Decimal('1'),
            cost=Decimal(str(-amount)),
        )
    )
    db.commit()
    db.refresh(acct)
    return float(acct.balance)


def raise_http_for_credits(exc: InsufficientCredits) -> None:
    raise HTTPException(
        status_code=402,
        detail={
            'code': 'insufficient_credits',
            'message': 'Bạn đã hết credits. Liên hệ admin để nạp thêm.',
            'balance': exc.balance,
            'required': exc.required,
        },
    )
