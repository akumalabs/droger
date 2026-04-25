from datetime import datetime, timezone
import asyncio
import html
import re
import time
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import security, crypto
from app.models import WizardJob
from . import do_service
from .token_service import resolve_token
from .windows import build_windows_user_data

DO_API_BASE = "https://api.digitalocean.com/v2"
DEFAULT_WIZARD_IMAGE = "debian-13-x64"
PASSWORD_BLOB_PREFIX = "[encpw]"
INSTALL_READY_CONSECUTIVE_SUCCESSES = 2
_install_probe_successes: dict[str, int] = {}
_ws_log_cache: dict[str, list[str]] = {}
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")


def _password_blob(password: str) -> str:
    return PASSWORD_BLOB_PREFIX + crypto.encrypt(password)


def _password_from_blob(blob: str | None) -> str | None:
    if not blob or not blob.startswith(PASSWORD_BLOB_PREFIX):
        return None
    encrypted = blob[len(PASSWORD_BLOB_PREFIX):]
    if not encrypted:
        return None
    try:
        return crypto.decrypt(encrypted)
    except Exception:
        return None


def _probe_key(user_id: str, token_id: str, droplet_id: int) -> str:
    return f"{user_id}:{token_id}:{droplet_id}"


async def _ping_host(host: str, timeout_sec: float = 1.5) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            str(int(timeout_sec)),
            host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=timeout_sec + 1.0)
        return proc.returncode == 0
    except Exception:
        return False


async def _tcp_open(host: str, port: int, timeout_sec: float = 1.5) -> bool:
    try:
        conn = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout_sec)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


def _append_ws_log(cache_key: str, message: str, limit: int = 200) -> str:
    lines = _ws_log_cache.get(cache_key, [])
    for line in (message or "").splitlines():
        text = ANSI_ESCAPE_RE.sub("", line).strip()
        if not text:
            continue
        if text == "***** START TRANS *****" and text in lines[-10:]:
            continue
        if lines and lines[-1] == text:
            continue
        lines.append(text)
    if len(lines) > limit:
        lines = lines[-limit:]
    _ws_log_cache[cache_key] = lines
    return "\n".join(lines[-120:])


async def _collect_ws_log_tail(public_ip: str, cache_key: str) -> str:
    try:
        import websockets
    except Exception:
        return _append_ws_log(cache_key, "")

    uri = f"ws://{public_ip}/"
    deadline = time.monotonic() + 3.0
    collected: list[str] = []
    try:
        async with websockets.connect(uri, open_timeout=2.0, close_timeout=1.0) as ws:
            while time.monotonic() < deadline:
                timeout_left = max(0.1, deadline - time.monotonic())
                try:
                    payload = await asyncio.wait_for(ws.recv(), timeout=min(0.4, timeout_left))
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8", errors="ignore")
                text = str(payload)
                if text:
                    collected.append(text)
                if len(collected) >= 120:
                    break
    except Exception:
        return _append_ws_log(cache_key, "")

    return _append_ws_log(cache_key, "\n".join(collected))


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
        command=_password_blob(rdp_password),
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
        "log_mode": "html",
        "ws_url": None,
        "windows_version": None,
        "rdp_port": None,
        "rdp_password": None,
        "ping_ok": False,
        "rdp_open": False,
        "install_complete": False,
        "install_message": "",
    }
    latest_job = await db.scalar(
        select(WizardJob)
        .where(
            WizardJob.user_id == user_id,
            WizardJob.token_id == token_id,
            WizardJob.droplet_id == droplet_id,
        )
        .order_by(WizardJob.created_at.desc())
        .limit(1)
    )
    probe_key = _probe_key(user_id, token_id, droplet_id)
    if latest_job:
        response["windows_version"] = latest_job.windows_version
        response["rdp_port"] = latest_job.rdp_port
        response["rdp_password"] = _password_from_blob(latest_job.command)

    if not public_ip:
        _install_probe_successes.pop(probe_key, None)
        _ws_log_cache.pop(probe_key, None)
        return response
    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", public_ip):
        _install_probe_successes.pop(probe_key, None)
        _ws_log_cache.pop(probe_key, None)
        return response
    rdp_port = response["rdp_port"]
    if isinstance(rdp_port, int) and 1 <= rdp_port <= 65535:
        ping_ok, rdp_open = await asyncio.gather(
            _ping_host(public_ip),
            _tcp_open(public_ip, rdp_port),
        )
        response["ping_ok"] = ping_ok
        response["rdp_open"] = rdp_open
        if ping_ok and rdp_open:
            _install_probe_successes[probe_key] = _install_probe_successes.get(probe_key, 0) + 1
            if _install_probe_successes[probe_key] >= INSTALL_READY_CONSECUTIVE_SUCCESSES:
                response["install_complete"] = True
                response["install_message"] = "Windows installation complete. You should be able to access it now."
        else:
            _install_probe_successes[probe_key] = 0
    else:
        _install_probe_successes.pop(probe_key, None)

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            progress = await client.get(f"http://{public_ip}/")
        if progress.status_code >= 400:
            return response
        text = progress.text or ""
        if "Droger Windows auto-install" in text:
            response["progress_ready"] = True
            response["log_tail"] = _tail_log_from_progress_html(text)
            return response
        if "<title>Reinstall Logs</title>" in text or "ReconnectingWebSocket" in text:
            response["progress_ready"] = True
            response["log_mode"] = "ws"
            response["ws_url"] = f"ws://{public_ip}/"
            response["log_tail"] = await _collect_ws_log_tail(public_ip, probe_key)
            return response
    except Exception:
        return response
    return response


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
