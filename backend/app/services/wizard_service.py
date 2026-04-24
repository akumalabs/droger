from datetime import datetime, timezone
import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import security
from app.models import WizardJob
from .token_service import resolve_token
from .windows import build_windows_user_data

DO_API_BASE = "https://api.digitalocean.com/v2"


async def deploy_windows(
    db: AsyncSession,
    user_id: str,
    token_id: str,
    name: str,
    region: str,
    size: str,
    image: str,
    ssh_keys: list[str] | None,
    windows_version: str,
    rdp_password: str,
    rdp_port: int,
) -> dict:
    token = await resolve_token(db, user_id, token_id)
    user_data = build_windows_user_data(windows_version, rdp_password, rdp_port)
    body: dict[str, object] = {
        "name": name,
        "region": region,
        "size": size,
        "image": image,
        "backups": False,
        "ipv6": False,
        "monitoring": True,
        "tags": ["droplet-manager", "windows-auto-install"],
        "user_data": user_data,
    }
    if ssh_keys:
        body["ssh_keys"] = ssh_keys
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{DO_API_BASE}/droplets",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
    if response.status_code >= 400:
        try:
            detail = response.json().get("message")
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail or "DO error")
    droplet = response.json().get("droplet", {})
    job = WizardJob(
        job_id=security.new_job_id(),
        user_id=user_id,
        token_id=token_id,
        droplet_id=droplet.get("id"),
        windows_version=windows_version,
        rdp_port=rdp_port,
        command="[hidden:auto-executed-via-user-data]",
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()
    return {
        "droplet": droplet,
        "auto_install": True,
        "windows_version": windows_version,
        "rdp_port": rdp_port,
    }
