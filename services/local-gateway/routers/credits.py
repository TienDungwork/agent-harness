from __future__ import annotations

from auth.deps import require_admin, require_user
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from storage.models import CreditAccount, User, get_db
from storage.users import AuthUser, create_local_user, to_auth_user

router = APIRouter(tags=['credits'])


class CreditBalance(BaseModel):
    balance: float
    credit_limit: float


class SetCreditsRequest(BaseModel):
    balance: float | None = None
    delta: float | None = None
    credit_limit: float | None = None


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: str | None = None
    is_admin: bool = False
    initial_credits: float = 100.0


class UserSummary(BaseModel):
    id: str
    username: str
    email: str | None
    is_admin: bool
    is_active: bool
    credit_balance: float
    credit_limit: float


@router.post('/api/admin/users', response_model=UserSummary)
async def create_user(
    body: CreateUserRequest,
    _: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserSummary:
    try:
        user = create_local_user(
            db,
            username=body.username.strip(),
            password=body.password,
            email=body.email,
            is_admin=body.is_admin,
            initial_credits=body.initial_credits,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    auth = to_auth_user(user)
    lim = (
        float(user.credit_account.credit_limit)
        if user.credit_account
        else body.initial_credits
    )
    return UserSummary(
        id=auth.id,
        username=auth.username,
        email=auth.email,
        is_admin=auth.is_admin,
        is_active=True,
        credit_balance=auth.credit_balance,
        credit_limit=float(lim),
    )


@router.get('/api/credits/me', response_model=CreditBalance)
async def my_credits(
    user: AuthUser = Depends(require_user), db: Session = Depends(get_db)
) -> CreditBalance:
    acct = (
        db.query(CreditAccount).filter(CreditAccount.user_id == user.id).one_or_none()
    )
    if acct is None:
        return CreditBalance(balance=0.0, credit_limit=0.0)
    return CreditBalance(
        balance=float(acct.balance), credit_limit=float(acct.credit_limit)
    )


@router.get('/api/admin/users', response_model=list[UserSummary])
async def list_users(
    _: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserSummary]:
    users = db.query(User).order_by(User.username).all()
    out: list[UserSummary] = []
    for u in users:
        bal = float(u.credit_account.balance) if u.credit_account else 0.0
        lim = float(u.credit_account.credit_limit) if u.credit_account else 0.0
        out.append(
            UserSummary(
                id=u.id,
                username=u.username,
                email=u.email,
                is_admin=u.is_admin,
                is_active=u.is_active,
                credit_balance=bal,
                credit_limit=lim,
            )
        )
    return out


@router.post('/api/admin/users/{user_id}/credits', response_model=CreditBalance)
async def set_credits(
    user_id: str,
    body: SetCreditsRequest,
    _: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CreditBalance:
    from decimal import Decimal

    acct = (
        db.query(CreditAccount).filter(CreditAccount.user_id == user_id).one_or_none()
    )
    if acct is None:
        raise HTTPException(status_code=404, detail='User credits not found')
    if body.balance is not None:
        acct.balance = Decimal(str(body.balance))
    if body.delta is not None:
        acct.balance = Decimal(str(acct.balance)) + Decimal(str(body.delta))
    if body.credit_limit is not None:
        acct.credit_limit = Decimal(str(body.credit_limit))
    if float(acct.balance) < 0:
        raise HTTPException(status_code=400, detail='balance cannot be negative')
    db.commit()
    db.refresh(acct)
    return CreditBalance(
        balance=float(acct.balance), credit_limit=float(acct.credit_limit)
    )


@router.post('/api/admin/users/{user_id}/disable')
async def disable_user(
    user_id: str,
    _: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail='User not found')
    user.is_active = False
    db.commit()
    return {'ok': True}


@router.post('/api/admin/users/{user_id}/enable')
async def enable_user(
    user_id: str,
    _: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail='User not found')
    user.is_active = True
    db.commit()
    return {'ok': True}
