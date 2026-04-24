from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.deps import current_user
from app.services import do_service, token_service

router = APIRouter(prefix="/api/do", tags=["do-proxy"])


async def _tok(user_id: str, token_id: str | None, db: AsyncSession) -> str:
    if not token_id:
        raise HTTPException(status_code=400, detail="token_id query param is required")
    return await token_service.resolve_token(db, user_id, token_id)


class CreateDropletReq(BaseModel):
    name: str
    region: str
    size: str
    image: str
    ssh_keys: list[str] | None = None
    backups: bool = False
    ipv6: bool = False
    monitoring: bool = True
    tags: list[str] | None = None
    user_data: str | None = None


class DropletActionReq(BaseModel):
    action_type: str
    image: str | None = None


class SnapshotReq(BaseModel):
    name: str = Field(min_length=1)


ALLOWED_ACTIONS = {
    "power_on",
    "power_off",
    "shutdown",
    "reboot",
    "power_cycle",
    "rebuild",
    "enable_ipv6",
    "enable_backups",
    "disable_backups",
    "password_reset",
}


@router.get("/account")
async def do_account(token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", "/account", token)


@router.get("/droplets")
async def list_droplets(token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", "/droplets", token, params={"per_page": 200})


@router.get("/droplets/{droplet_id}")
async def get_droplet(droplet_id: int, token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", f"/droplets/{droplet_id}", token)


@router.post("/droplets")
async def create_droplet(payload: CreateDropletReq, token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("POST", "/droplets", token, json_body=payload.model_dump(exclude_none=True))


@router.delete("/droplets/{droplet_id}")
async def delete_droplet(droplet_id: int, token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("DELETE", f"/droplets/{droplet_id}", token)


@router.post("/droplets/{droplet_id}/actions")
async def droplet_action(
    droplet_id: int,
    payload: DropletActionReq,
    token_id: str,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await _tok(user.user_id, token_id, db)
    if payload.action_type not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {payload.action_type}")
    body: dict[str, Any] = {"type": payload.action_type}
    if payload.action_type == "rebuild":
        if not payload.image:
            raise HTTPException(status_code=400, detail="image is required for rebuild")
        body["image"] = payload.image
    return await do_service.do_request("POST", f"/droplets/{droplet_id}/actions", token, json_body=body)


@router.get("/droplets/{droplet_id}/snapshots")
async def droplet_snapshots(droplet_id: int, token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", f"/droplets/{droplet_id}/snapshots", token)


@router.post("/droplets/{droplet_id}/snapshot")
async def droplet_snapshot(
    droplet_id: int,
    payload: SnapshotReq,
    token_id: str,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request(
        "POST",
        f"/droplets/{droplet_id}/actions",
        token,
        json_body={"type": "snapshot", "name": payload.name},
    )


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("DELETE", f"/snapshots/{snapshot_id}", token)


@router.get("/regions")
async def regions(token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", "/regions", token, params={"per_page": 200})


@router.get("/sizes")
async def sizes(token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", "/sizes", token, params={"per_page": 200})


@router.get("/images")
async def images(token_id: str, type: str = "distribution", user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", "/images", token, params={"type": type, "per_page": 200})


@router.get("/ssh_keys")
async def ssh_keys(token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    token = await _tok(user.user_id, token_id, db)
    return await do_service.do_request("GET", "/account/keys", token, params={"per_page": 200})
