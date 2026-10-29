import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.db import get_session
from app.models import Subscription, User
from app.outbox import add_event
from app.schemas import Credentials, SubscriptionIn
from app.security import create_token, decode_token, hash_password, verify_password

auth_router = APIRouter(prefix="/auth", tags=["auth"])
sub_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
bearer = HTTPBearer()


@auth_router.post("/register", status_code=201)
async def register(body: Credentials, session=Depends(get_session)):
    email = body.email.lower()
    if await session.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "email already registered")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    await session.commit()
    return {"id": str(user.id), "email": user.email}


@auth_router.post("/login")
async def login(body: Credentials, session=Depends(get_session)):
    user = await session.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    return {"access_token": create_token(str(user.id)), "token_type": "bearer"}


async def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer), session=Depends(get_session)
) -> User:
    try:
        user = await session.get(User, uuid.UUID(decode_token(creds.credentials)))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "invalid token")
    if not user:
        raise HTTPException(401, "invalid token")
    return user


def _dict(s: Subscription) -> dict:
    return {
        "subscription_id": str(s.id),
        "user_id": str(s.user_id),
        "skills": s.skills,
        "location": s.location,
        "min_salary": s.min_salary,
        "currency": s.currency,
        "telegram_chat_id": s.telegram_chat_id,
        "active": s.active,
    }


def _apply(sub: Subscription, body: SubscriptionIn):
    sub.skills = sorted({x.strip().lower() for x in body.skills if x.strip()})
    sub.location = body.location
    sub.min_salary = body.min_salary
    sub.currency = body.currency.upper() if body.currency else None
    sub.telegram_chat_id = body.telegram_chat_id
    sub.active = body.active


async def _owned(session, sub_id: uuid.UUID, user: User) -> Subscription:
    sub = await session.scalar(
        select(Subscription).where(Subscription.id == sub_id, Subscription.user_id == user.id)
    )
    if not sub:
        raise HTTPException(404, "subscription not found")
    return sub


@sub_router.post("", status_code=201)
async def create_subscription(body: SubscriptionIn, user=Depends(current_user), session=Depends(get_session)):
    sub = Subscription(id=uuid.uuid4(), user_id=user.id)
    _apply(sub, body)
    session.add(sub)
    add_event(session, str(sub.id), "subscription.upserted", _dict(sub))
    await session.commit()  # subscription and outbox row are committed atomically
    return _dict(sub)


@sub_router.get("")
async def list_subscriptions(user=Depends(current_user), session=Depends(get_session)):
    rows = (await session.scalars(select(Subscription).where(Subscription.user_id == user.id))).all()
    return [_dict(s) for s in rows]


@sub_router.put("/{sub_id}")
async def update_subscription(sub_id: uuid.UUID, body: SubscriptionIn, user=Depends(current_user), session=Depends(get_session)):
    sub = await _owned(session, sub_id, user)
    _apply(sub, body)
    add_event(session, str(sub.id), "subscription.upserted", _dict(sub))
    await session.commit()
    return _dict(sub)


@sub_router.delete("/{sub_id}", status_code=204)
async def delete_subscription(sub_id: uuid.UUID, user=Depends(current_user), session=Depends(get_session)):
    sub = await _owned(session, sub_id, user)
    await session.delete(sub)
    add_event(session, str(sub_id), "subscription.deleted", {"subscription_id": str(sub_id)})
    await session.commit()
