from datetime import datetime, timezone
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import crypto, security
from app.models import DOToken

DO_API_BASE = "https://api.digitalocean.com/v2"


def _public(token: DOToken) -> dict:
    return {
        "id": token.token_id,
        "name": token.name,
        "do_email": token.do_email,
        "do_uuid": token.do_uuid,
        "droplet_limit": token.droplet_limit,
        "created_at": token.created_at.isoformat() if token.created_at else None,
        "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
    }


async def validate_do_token(do_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{DO_API_BASE}/account",
            headers={"Authorization": f"Bearer {do_token}"},
        )
    if response.status_code == 401:
        raise HTTPException(status_code=400, detail="DigitalOcean rejected this token")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"DO error: {response.text[:120]}")
    return response.json().get("account", {})


async def list_tokens(db: AsyncSession, user_id: str) -> dict:
    rows = await db.scalars(select(DOToken).where(DOToken.user_id == user_id).order_by(DOToken.created_at))
    return {"tokens": [_public(row) for row in rows.all()]}


async def add_token(db: AsyncSession, user_id: str, name: str, raw_token: str) -> dict:
    account = await validate_do_token(raw_token)
    row = DOToken(
        token_id=security.new_token_id(),
        user_id=user_id,
        name=name.strip(),
        token_encrypted=crypto.encrypt(raw_token.strip()),
        do_email=account.get("email"),
        do_uuid=account.get("uuid"),
        droplet_limit=account.get("droplet_limit"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _public(row)


async def rename_token(db: AsyncSession, user_id: str, token_id: str, name: str) -> dict:
    row = await db.scalar(select(DOToken).where(DOToken.token_id == token_id, DOToken.user_id == user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    row.name = name.strip()
    await db.commit()
    await db.refresh(row)
    return _public(row)


async def delete_token(db: AsyncSession, user_id: str, token_id: str) -> dict:
    row = await db.scalar(select(DOToken).where(DOToken.token_id == token_id, DOToken.user_id == user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


async def resolve_token(db: AsyncSession, user_id: str, token_id: str) -> str:
    row = await db.scalar(select(DOToken).where(DOToken.token_id == token_id, DOToken.user_id == user_id))
    if not row:
        raise HTTPException(status_code=404, detail="DO token not found")
    row.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return crypto.decrypt(row.token_encrypted)
