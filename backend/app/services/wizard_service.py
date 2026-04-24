from datetime import datetime, timezone
import html
import re
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import security
from app.models import WizardJob
from . import do_service
from .token_service import resolve_token
from .windows import build_windows_user_data

DO_API_BASE = "https://api.digitalocean.com/v2"
DEFAULT_WIZARD_IMAGE = "debian-13-x64"


async def deploy_windows(
    db: AsyncSession,
    user_id: str,
    token_id: str,
    name: str,
    region: str,
    size: str,
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
        "image": DEFAULT_WIZARD_IMAGE,
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


def _extract_public_ip(droplet: dict) -> str | None:
    for item in (droplet.get("networks") or {}).get("v4", []):
        if item.get("type") == "public":
            return item.get("ip_address")
    return None


def _tail_log_from_progress_html(html_text: str) -> str:
    match = re.search(r"<pre>(.*?)</pre>", html_text, flags=re.IGNORECASE | re.DOTALL)
    content = match.group(1) if match else html_text
    decoded = html.unescape(content)
    lines = decoded.splitlines()
    return "\n".join(lines[-120:]).strip()


async def get_install_progress(db: AsyncSession, user_id: str, token_id: str, droplet_id: int) -> dict:
    token = await resolve_token(db, user_id, token_id)
    payload = await do_service.do_request("GET", f"/droplets/{droplet_id}", token)
    droplet = payload.get("droplet", {})
    public_ip = _extract_public_ip(droplet)
    response = {
        "droplet": droplet,
        "public_ip": public_ip,
        "droplet_status": droplet.get("status"),
        "progress_ready": False,
        "log_tail": "",
    }
    if not public_ip:
        return response
    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", public_ip):
        return response
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            progress = await client.get(f"http://{public_ip}/")
        if progress.status_code >= 400:
            return response
        text = progress.text or ""
        if "Droger Windows auto-install" not in text:
            return response
        response["progress_ready"] = True
        response["log_tail"] = _tail_log_from_progress_html(text)
    except Exception:
        return response
    return response


async def reinstall_windows(
    db: AsyncSession,
    user_id: str,
    token_id: str,
    droplet_id: int,
    windows_version: str,
    rdp_password: str,
    rdp_port: int,
) -> dict:
    token = await resolve_token(db, user_id, token_id)
    payload = await do_service.do_request("GET", f"/droplets/{droplet_id}", token)
    droplet = payload.get("droplet", {})
    if not droplet:
        raise HTTPException(status_code=404, detail="Droplet not found")
    if droplet.get("locked"):
        raise HTTPException(status_code=409, detail="Droplet is locked by another action")
    if droplet.get("status") != "off":
        raise HTTPException(status_code=409, detail="Droplet must be powered off before rebuild")

    user_data = build_windows_user_data(windows_version, rdp_password, rdp_port)
    action_response = await do_service.do_request(
        "POST",
        f"/droplets/{droplet_id}/actions",
        token,
        json_body={
            "type": "rebuild",
            "image": DEFAULT_WIZARD_IMAGE,
            "user_data": user_data,
        },
    )

    job = WizardJob(
        job_id=security.new_job_id(),
        user_id=user_id,
        token_id=token_id,
        droplet_id=droplet_id,
        windows_version=windows_version,
        rdp_port=rdp_port,
        command="[hidden:auto-reinstall-via-rebuild]",
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.commit()

    return {
        "ok": True,
        "droplet_id": droplet_id,
        "action": action_response.get("action", action_response),
        "image": DEFAULT_WIZARD_IMAGE,
        "windows_version": windows_version,
        "rdp_port": rdp_port,
        "note": "Droplet rebuild to Debian 13 started with Windows auto-install.",
    }


async def list_recent_jobs(db: AsyncSession, user_id: str, limit: int = 20) -> dict:
    rows = await db.scalars(
        select(WizardJob)
        .where(WizardJob.user_id == user_id)
        .order_by(WizardJob.created_at.desc())
        .limit(limit)
    )
    jobs = []
    for row in rows.all():
        jobs.append(
            {
                "job_id": row.job_id,
                "droplet_id": row.droplet_id,
                "windows_version": row.windows_version,
                "rdp_port": row.rdp_port,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return {"jobs": jobs}
