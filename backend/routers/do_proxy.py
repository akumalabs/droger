"""Thin proxy over DigitalOcean API v2. All endpoints require auth + ?token_id."""
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import current_user
from routers.tokens import resolve_token

DO_API_BASE = "https://api.digitalocean.com/v2"

router = APIRouter(prefix="/api/do", tags=["do-proxy"])


async def _do(method: str, path: str, token: str, params=None, json_body=None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.request(method, f"{DO_API_BASE}{path}", headers=headers, params=params, json=json_body)
    if r.status_code == 204:
        return {"ok": True}
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=data.get("message") if isinstance(data, dict) else str(data))
    return data


async def _tok(user: dict, token_id: Optional[str]) -> str:
    if not token_id:
        raise HTTPException(status_code=400, detail="token_id query param is required")
    return await resolve_token(user["user_id"], token_id)


# Models
class CreateDropletReq(BaseModel):
    name: str
    region: str
    size: str
    image: str
    ssh_keys: Optional[List[str]] = None
    backups: bool = False
    ipv6: bool = False
    monitoring: bool = True
    tags: Optional[List[str]] = None
    user_data: Optional[str] = None


class DropletActionReq(BaseModel):
    action_type: str
    image: Optional[str] = None


class SnapshotReq(BaseModel):
    name: str = Field(min_length=1)


ALLOWED_ACTIONS = {
    "power_on", "power_off", "shutdown", "reboot", "power_cycle",
    "rebuild", "enable_ipv6", "enable_backups", "disable_backups", "password_reset",
}


@router.get("/account")
async def do_account(token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", "/account", await _tok(user, token_id))


@router.get("/droplets")
async def list_droplets(token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", "/droplets", await _tok(user, token_id), params={"per_page": 200})


@router.get("/droplets/{droplet_id}")
async def get_droplet(droplet_id: int, token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", f"/droplets/{droplet_id}", await _tok(user, token_id))


@router.post("/droplets")
async def create_droplet(payload: CreateDropletReq, token_id: str, user: dict = Depends(current_user)):
    return await _do("POST", "/droplets", await _tok(user, token_id), json_body=payload.model_dump(exclude_none=True))


@router.delete("/droplets/{droplet_id}")
async def delete_droplet(droplet_id: int, token_id: str, user: dict = Depends(current_user)):
    return await _do("DELETE", f"/droplets/{droplet_id}", await _tok(user, token_id))


@router.post("/droplets/{droplet_id}/actions")
async def droplet_action(droplet_id: int, payload: DropletActionReq, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    if payload.action_type not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {payload.action_type}")
    body: Dict[str, Any] = {"type": payload.action_type}
    if payload.action_type == "rebuild":
        if not payload.image:
            raise HTTPException(status_code=400, detail="image is required for rebuild")
        body["image"] = payload.image
    return await _do("POST", f"/droplets/{droplet_id}/actions", t, json_body=body)


@router.get("/droplets/{droplet_id}/snapshots")
async def droplet_snapshots(droplet_id: int, token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", f"/droplets/{droplet_id}/snapshots", await _tok(user, token_id))


@router.post("/droplets/{droplet_id}/snapshot")
async def droplet_snapshot(droplet_id: int, payload: SnapshotReq, token_id: str, user: dict = Depends(current_user)):
    return await _do(
        "POST", f"/droplets/{droplet_id}/actions", await _tok(user, token_id),
        json_body={"type": "snapshot", "name": payload.name},
    )


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, token_id: str, user: dict = Depends(current_user)):
    return await _do("DELETE", f"/snapshots/{snapshot_id}", await _tok(user, token_id))


@router.get("/regions")
async def regions(token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", "/regions", await _tok(user, token_id), params={"per_page": 200})


@router.get("/sizes")
async def sizes(token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", "/sizes", await _tok(user, token_id), params={"per_page": 200})


@router.get("/images")
async def images(token_id: str, type: str = "distribution", user: dict = Depends(current_user)):
    return await _do("GET", "/images", await _tok(user, token_id), params={"type": type, "per_page": 200})


@router.get("/ssh_keys")
async def ssh_keys(token_id: str, user: dict = Depends(current_user)):
    return await _do("GET", "/account/keys", await _tok(user, token_id), params={"per_page": 200})
