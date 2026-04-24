from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
import jwt
from app.core import security
from app.models import EmailVerificationToken, PasswordResetToken, User
from . import mail_service


def public_user(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
        "auth_provider": user.auth_provider,
        "email_verified": bool(user.email_verified),
    }


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower().strip())
    return await db.scalar(stmt)


async def create_user(db: AsyncSession, email: str, password: str, name: str | None = None) -> User:
    normalized = email.lower().strip()
    existing = await get_user_by_email(db, normalized)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        user_id=security.new_user_id(),
        email=normalized,
        name=name or normalized.split("@")[0],
        password_hash=security.hash_password(password),
        auth_provider="email",
        email_verified=False,
        role="user",
    )
    db.add(user)
    await db.flush()
    token = await create_email_verification_token(db, user.user_id, user.email)
    await db.commit()
    await db.refresh(user)
    await send_verification_email(user.email, token)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not user.password_hash:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user


async def create_email_verification_token(db: AsyncSession, user_id: str, email: str) -> str:
    import secrets

    token = secrets.token_urlsafe(32)
    row = EmailVerificationToken(
        token=token,
        user_id=user_id,
        email=email,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(row)
    await db.flush()
    return token


async def send_verification_email(email: str, token: str) -> bool:
    from app.core.config import get_settings

    settings = get_settings()
    link = f"{settings.frontend_url}/verify-email?token={token}"
    return await mail_service.send_verification_email(email, link)


async def verify_email_token(db: AsyncSession, token: str) -> None:
    row = await db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token == token))
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    if row.expires_at < datetime.now(timezone.utc):
        await db.delete(row)
        await db.commit()
        raise HTTPException(status_code=400, detail="Verification link expired")
    user = await db.scalar(select(User).where(User.user_id == row.user_id))
    if user:
        user.email_verified = True
    await db.delete(row)
    await db.commit()


async def resend_verification(db: AsyncSession, user: User) -> bool:
    if user.email_verified:
        return True
    await db.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.user_id))
    token = await create_email_verification_token(db, user.user_id, user.email)
    await db.commit()
    await send_verification_email(user.email, token)
    return False


async def create_password_reset(db: AsyncSession, email: str) -> None:
    import secrets

    user = await get_user_by_email(db, email)
    if not user or not user.password_hash:
        return
    token = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        token=token,
        user_id=user.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used=False,
    )
    db.add(row)
    await db.commit()
    from app.core.config import get_settings

    settings = get_settings()
    link = f"{settings.frontend_url}/reset-password?token={token}"
    await mail_service.send_password_reset_email(user.email, link)


async def apply_password_reset(db: AsyncSession, token: str, password: str) -> User | None:
    row = await db.scalar(select(PasswordResetToken).where(PasswordResetToken.token == token))
    if not row or row.used:
        raise HTTPException(status_code=400, detail="Invalid or already-used reset link")
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link expired")
    user = await db.scalar(select(User).where(User.user_id == row.user_id))
    if user:
        user.password_hash = security.hash_password(password)
    row.used = True
    await db.commit()
    return user


async def get_user_from_request(request: Request, db: AsyncSession) -> User:
    token = security.extract_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = security.decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = await db.scalar(select(User).where(User.user_id == payload.get("sub")))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
