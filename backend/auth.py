"""Auth module: unified login for JWT email/password + Emergent Google session.

Both paths resolve to the same users collection (custom user_id UUID) and
produce an httpOnly session cookie so downstream endpoints can authorise the
request without caring which method was used.
"""
from __future__ import annotations

import os
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import httpx
import jwt
from fastapi import HTTPException, Request, Response

JWT_ALGORITHM = "HS256"
ACCESS_TTL_MIN = 60 * 24  # 1 day (session feels long enough for a devtool)
REFRESH_TTL_DAYS = 7
GOOGLE_SESSION_TTL_DAYS = 7

EMERGENT_SESSION_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)


def _jwt_secret() -> str:
    s = os.environ.get("JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET not configured")
    return s


# ------------------------- password --------------------------- #
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ------------------------- JWT -------------------------------- #
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])


# ------------------------- Cookies ---------------------------- #
def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        "access_token", access,
        httponly=True, secure=True, samesite="none",
        max_age=ACCESS_TTL_MIN * 60, path="/",
    )
    response.set_cookie(
        "refresh_token", refresh,
        httponly=True, secure=True, samesite="none",
        max_age=REFRESH_TTL_DAYS * 86400, path="/",
    )


def set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        "session_token", session_token,
        httponly=True, secure=True, samesite="none",
        max_age=GOOGLE_SESSION_TTL_DAYS * 86400, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in ("access_token", "refresh_token", "session_token"):
        response.delete_cookie(name, path="/")


# ------------------------- Current user ------------------------ #
async def get_current_user(request: Request, db) -> dict:
    # 1. JWT access cookie / Bearer header
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:]
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") == "access":
                user = await db.users.find_one(
                    {"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0}
                )
                if user:
                    return user
        except jwt.ExpiredSignatureError:
            pass  # fall through to session check
        except jwt.InvalidTokenError:
            pass

    # 2. Emergent session cookie
    session_token = request.cookies.get("session_token")
    if session_token:
        session = await db.user_sessions.find_one(
            {"session_token": session_token}, {"_id": 0}
        )
        if session:
            expires_at = session.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at >= datetime.now(timezone.utc):
                user = await db.users.find_one(
                    {"user_id": session["user_id"]},
                    {"_id": 0, "password_hash": 0},
                )
                if user:
                    return user

    raise HTTPException(status_code=401, detail="Not authenticated")


# ------------------------- Emergent OAuth session exchange ----- #
async def exchange_emergent_session(session_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            EMERGENT_SESSION_URL,
            headers={"X-Session-ID": session_id},
        )
    if r.status_code >= 400:
        raise HTTPException(
            status_code=401, detail="Invalid Google session"
        )
    return r.json()


# ------------------------- Brute force ------------------------- #
LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15


async def check_lockout(db, identifier: str) -> None:
    doc = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if not doc:
        return
    if doc.get("count", 0) < LOCKOUT_THRESHOLD:
        return
    last = doc.get("last_attempt")
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last and datetime.now(timezone.utc) - last < timedelta(minutes=LOCKOUT_MINUTES):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in a few minutes.",
        )
    await db.login_attempts.delete_one({"identifier": identifier})


async def record_failed_attempt(db, identifier: str) -> None:
    now = datetime.now(timezone.utc)
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {
            "$inc": {"count": 1},
            "$set": {"last_attempt": now},
        },
        upsert=True,
    )


async def clear_attempts(db, identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})


def new_user_id() -> str:
    return f"user_{uuid.uuid4().hex[:16]}"


def new_session_token() -> str:
    return secrets.token_urlsafe(40)
