"""Deploy-Linux-then-Windows wizard."""
import secrets
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from db import db
from deps import current_user
from routers.tokens import resolve_token
from routers.windows import build_windows_command

DO_API_BASE = "https://api.digitalocean.com/v2"

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


class DeployWizardReq(BaseModel):
    token_id: str
    name: str = Field(min_length=1, max_length=60)
    region: str
    size: str
    image: str
    ssh_keys: Optional[List[str]] = None
    windows_version: str
    rdp_password: str = Field(min_length=6, max_length=64)
    rdp_port: int = 3389

    @field_validator("rdp_port")
    @classmethod
    def _port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("RDP port must be between 1 and 65535")
        return v


@router.post("/deploy-windows")
async def deploy_windows(payload: DeployWizardReq, user: dict = Depends(current_user)):
    t = await resolve_token(user["user_id"], payload.token_id)
    body = {
        "name": payload.name,
        "region": payload.region,
        "size": payload.size,
        "image": payload.image,
        "backups": False,
        "ipv6": False,
        "monitoring": True,
        "tags": ["droplet-manager", "windows-pending"],
    }
    if payload.ssh_keys:
        body["ssh_keys"] = payload.ssh_keys

    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            f"{DO_API_BASE}/droplets",
            headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"},
            json=body,
        )
    if r.status_code >= 400:
        try:
            detail = r.json().get("message")
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail or "DO error")
    droplet = r.json().get("droplet", {})
    command = build_windows_command(payload.windows_version, payload.rdp_password, payload.rdp_port)

    await db.wizard_jobs.insert_one({
        "job_id": f"job_{secrets.token_urlsafe(12)}",
        "user_id": user["user_id"],
        "token_id": payload.token_id,
        "droplet_id": droplet.get("id"),
        "windows_version": payload.windows_version,
        "rdp_port": payload.rdp_port,
        "command": command,
        "created_at": datetime.now(timezone.utc),
    })
    return {"droplet": droplet, "command": command}
