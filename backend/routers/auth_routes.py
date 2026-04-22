"""Auth endpoints: register, login, logout, refresh, Google OAuth, verification, password reset."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

import auth as auth_mod
import mailer
from db import db
from deps import current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

FRONTEND = os.environ.get("FRONTEND_URL", "")


# ---------- Models ---------- #
class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: Optional[str] = None


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class SessionReq(BaseModel):
    session_id: str


class ForgotReq(BaseModel):
    email: EmailStr


class ResetReq(BaseModel):
    token: str
    password: str = Field(min_length=6, max_length=128)


# ---------- Helpers ---------- #
def _public_user(u: dict) -> dict:
    return {
        "user_id": u["user_id"],
        "email": u["email"],
        "name": u.get("name"),
        "picture": u.get("picture"),
        "role": u.get("role", "user"),
        "auth_provider": u.get("auth_provider", "email"),
        "email_verified": bool(u.get("email_verified", False)),
    }


async def _create_verification(user_id: str, email: str) -> str:
    token = secrets.token_urlsafe(32)
    await db.email_verification_tokens.insert_one({
        "token": token,
        "user_id": user_id,
        "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "created_at": datetime.now(timezone.utc),
    })
    return token


async def _send_verification(email: str, token: str) -> None:
    link = f"{FRONTEND}/verify-email?token={token}"
    await mailer.send_verification_email(email, link)


# ---------- Endpoints ---------- #
@router.post("/register")
async def register(payload: RegisterReq, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = {
        "user_id": auth_mod.new_user_id(),
        "email": email,
        "name": payload.name or email.split("@")[0],
        "password_hash": auth_mod.hash_password(payload.password),
        "auth_provider": "email",
        "email_verified": False,
        "role": "user",
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(user_doc)

    # send verification asynchronously
    token = await _create_verification(user_doc["user_id"], email)
    await _send_verification(email, token)

    access = auth_mod.create_access_token(user_doc["user_id"], email)
    refresh = auth_mod.create_refresh_token(user_doc["user_id"])
    auth_mod.set_auth_cookies(response, access, refresh)
    return _public_user(user_doc)


@router.post("/login")
async def login(payload: LoginReq, response: Response):
    email = payload.email.lower().strip()
    identifier = f"email:{email}"
    await auth_mod.check_lockout(db, identifier)

    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        await auth_mod.record_failed_attempt(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not auth_mod.verify_password(payload.password, user["password_hash"]):
        await auth_mod.record_failed_attempt(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await auth_mod.clear_attempts(db, identifier)
    access = auth_mod.create_access_token(user["user_id"], email)
    refresh = auth_mod.create_refresh_token(user["user_id"])
    auth_mod.set_auth_cookies(response, access, refresh)
    return _public_user(user)


@router.post("/session")
async def google_session(payload: SessionReq, response: Response):
    data = await auth_mod.exchange_emergent_session(payload.session_id)
    email = (data.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="No email returned by provider")

    user = await db.users.find_one({"email": email})
    if not user:
        user = {
            "user_id": auth_mod.new_user_id(),
            "email": email,
            "name": data.get("name") or email.split("@")[0],
            "picture": data.get("picture"),
            "auth_provider": "google",
            "email_verified": True,  # google verified
            "role": "user",
            "created_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(user)
    else:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "name": data.get("name") or user.get("name"),
                "picture": data.get("picture") or user.get("picture"),
                "email_verified": True,
                "auth_provider": "both" if user.get("auth_provider") == "email" else "google",
            }},
        )
        user = await db.users.find_one({"user_id": user["user_id"]})

    session_token = auth_mod.new_session_token()
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    auth_mod.set_session_cookie(response, session_token)
    return _public_user(user)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return _public_user(user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    st = request.cookies.get("session_token")
    if st:
        await db.user_sessions.delete_one({"session_token": st})
    auth_mod.clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = auth_mod.decode_token(rt)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    access = auth_mod.create_access_token(user["user_id"], user["email"])
    response.set_cookie(
        "access_token", access, httponly=True, secure=True, samesite="none",
        max_age=auth_mod.ACCESS_TTL_MIN * 60, path="/",
    )
    return {"ok": True}


# ---------- Email verification ---------- #
class VerifyEmailReq(BaseModel):
    token: str


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailReq):
    doc = await db.email_verification_tokens.find_one(
        {"token": payload.token}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    expires = doc.get("expires_at")
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < datetime.now(timezone.utc):
        await db.email_verification_tokens.delete_one({"token": payload.token})
        raise HTTPException(status_code=400, detail="Verification link expired")

    await db.users.update_one(
        {"user_id": doc["user_id"]},
        {"$set": {"email_verified": True}},
    )
    await db.email_verification_tokens.delete_one({"token": payload.token})
    return {"ok": True}


@router.post("/resend-verification")
async def resend_verification(user: dict = Depends(current_user)):
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    # invalidate old tokens for same user
    await db.email_verification_tokens.delete_many({"user_id": user["user_id"]})
    token = await _create_verification(user["user_id"], user["email"])
    sent = await _send_verification(user["email"], token)
    return {"ok": True, "sent": bool(sent)}


# ---------- Password reset ---------- #
@router.post("/forgot-password")
async def forgot_password(payload: ForgotReq):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Always return ok to avoid email enumeration; only send when user exists
    if user and user.get("password_hash"):
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False,
            "created_at": datetime.now(timezone.utc),
        })
        link = f"{FRONTEND}/reset-password?token={token}"
        await mailer.send_password_reset_email(email, link)
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(payload: ResetReq):
    doc = await db.password_reset_tokens.find_one({"token": payload.token}, {"_id": 0})
    if not doc or doc.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or already-used reset link")
    expires = doc.get("expires_at")
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link expired")

    new_hash = auth_mod.hash_password(payload.password)
    await db.users.update_one(
        {"user_id": doc["user_id"]},
        {"$set": {"password_hash": new_hash}},
    )
    await db.password_reset_tokens.update_one(
        {"token": payload.token}, {"$set": {"used": True}}
    )
    # clear any active lockouts
    user = await db.users.find_one({"user_id": doc["user_id"]}, {"_id": 0, "email": 1})
    if user:
        await auth_mod.clear_attempts(db, f"email:{user['email']}")
    return {"ok": True}
