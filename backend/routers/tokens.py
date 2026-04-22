"""DO token vault: per-user, encrypted at rest."""
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import crypto_utils as cu
from db import db
from deps import current_user

DO_API_BASE = "https://api.digitalocean.com/v2"

router = APIRouter(prefix="/api/do-tokens", tags=["do-tokens"])


class AddTokenReq(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    token: str = Field(min_length=10)


class RenameTokenReq(BaseModel):
    name: str = Field(min_length=1, max_length=50)


async def _validate_do_token(do_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(
            f"{DO_API_BASE}/account",
            headers={"Authorization": f"Bearer {do_token}"},
        )
    if r.status_code == 401:
        raise HTTPException(status_code=400, detail="DigitalOcean rejected this token")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"DO error: {r.text[:120]}")
    return r.json().get("account", {})


def _public(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "name": doc["name"],
        "do_email": doc.get("do_email"),
        "do_uuid": doc.get("do_uuid"),
        "droplet_limit": doc.get("droplet_limit"),
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
        "last_used_at": doc.get("last_used_at").isoformat() if isinstance(doc.get("last_used_at"), datetime) else doc.get("last_used_at"),
    }


@router.get("")
async def list_tokens(user: dict = Depends(current_user)):
    docs = await db.do_tokens.find(
        {"user_id": user["user_id"]}, {"_id": 0, "token_encrypted": 0}
    ).to_list(200)
    docs.sort(key=lambda d: d.get("created_at") or "")
    return {"tokens": [_public(d) for d in docs]}


@router.post("")
async def add_token(payload: AddTokenReq, user: dict = Depends(current_user)):
    account = await _validate_do_token(payload.token.strip())
    doc = {
        "id": f"tok_{secrets.token_urlsafe(12)}",
        "user_id": user["user_id"],
        "name": payload.name.strip(),
        "token_encrypted": cu.encrypt(payload.token.strip()),
        "do_email": account.get("email"),
        "do_uuid": account.get("uuid"),
        "droplet_limit": account.get("droplet_limit"),
        "created_at": datetime.now(timezone.utc),
    }
    await db.do_tokens.insert_one(doc)
    return _public(doc)


@router.patch("/{token_id}")
async def rename_token(token_id: str, payload: RenameTokenReq, user: dict = Depends(current_user)):
    res = await db.do_tokens.update_one(
        {"id": token_id, "user_id": user["user_id"]},
        {"$set": {"name": payload.name.strip()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    doc = await db.do_tokens.find_one({"id": token_id}, {"_id": 0, "token_encrypted": 0})
    return _public(doc)


@router.delete("/{token_id}")
async def delete_token(token_id: str, user: dict = Depends(current_user)):
    res = await db.do_tokens.delete_one({"id": token_id, "user_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"ok": True}


# ---- Shared helper used by /do proxy and wizard ----
async def resolve_token(user_id: str, token_id: str) -> str:
    doc = await db.do_tokens.find_one({"id": token_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="DO token not found")
    await db.do_tokens.update_one(
        {"id": token_id},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )
    return cu.decrypt(doc["token_encrypted"])
