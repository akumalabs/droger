from datetime import timezone
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import security
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import current_user
from app.core.redis import get_redis
from app.middleware.rate_limit import enforce_rate_limit
from app.security.lockout import check_lockout, clear_attempts, record_failed_attempt
from app.services import auth_service
from .schemas import ForgotPasswordReq, LoginReq, RegisterReq, ResetPasswordReq, VerifyEmailReq

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(payload: RegisterReq, response: Response, db: AsyncSession = Depends(get_db)):
    user = await auth_service.create_user(db, payload.email, payload.password, payload.name)
    access = security.create_access_token(user.user_id, user.email)
    refresh = security.create_refresh_token(user.user_id)
    security.set_auth_cookies(response, access, refresh)
    return auth_service.public_user(user)


@router.post("/login")
async def login(payload: LoginReq, response: Response, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    redis_client = get_redis()
    email = payload.email.lower().strip()
    identifier = f"email:{email}"
    await enforce_rate_limit(redis_client, "login", identifier, settings.login_rate_limit_per_minute, 60)
    await check_lockout(redis_client, identifier)
    user = await auth_service.authenticate_user(db, email, payload.password)
    if not user:
        await record_failed_attempt(redis_client, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await clear_attempts(redis_client, identifier)
    access = security.create_access_token(user.user_id, user.email)
    refresh = security.create_refresh_token(user.user_id)
    security.set_auth_cookies(response, access, refresh)
    return auth_service.public_user(user)


@router.get("/me")
async def me(user=Depends(current_user)):
    return auth_service.public_user(user)


@router.post("/logout")
async def logout(response: Response):
    security.clear_auth_cookies(response)
    return {"ok": True}


@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = security.decode_token(rt)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await auth_service.get_user_by_email(db, payload.get("email", "")) if payload.get("email") else None
    if not user:
        from sqlalchemy import select
        from app.models import User

        user = await db.scalar(select(User).where(User.user_id == payload.get("sub")))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    access = security.create_access_token(user.user_id, user.email)
    response.set_cookie(
        "access_token",
        access,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite=get_settings().cookie_samesite,
        max_age=get_settings().access_ttl_minutes * 60,
        path="/",
    )
    return {"ok": True}


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailReq, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email_token(db, payload.token)
    return {"ok": True}


@router.post("/resend-verification")
async def resend_verification(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    redis_client = get_redis()
    identifier = f"user:{user.user_id}"
    await enforce_rate_limit(
        redis_client,
        "resend-verification",
        identifier,
        settings.resend_verification_rate_limit_per_hour,
        3600,
    )
    already_verified = await auth_service.resend_verification(db, user)
    if already_verified:
        return {"ok": True, "already_verified": True}
    return {"ok": True, "sent": True}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordReq, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    redis_client = get_redis()
    email = payload.email.lower().strip()
    await enforce_rate_limit(redis_client, "forgot-password", f"email:{email}", settings.forgot_rate_limit_per_hour, 3600)
    await auth_service.create_password_reset(db, email)
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordReq, db: AsyncSession = Depends(get_db)):
    user = await auth_service.apply_password_reset(db, payload.token, payload.password)
    if user:
        redis_client = get_redis()
        await clear_attempts(redis_client, f"email:{user.email}")
    return {"ok": True}
