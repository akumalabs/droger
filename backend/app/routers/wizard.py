from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.deps import current_user
from app.services import wizard_service

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


class DeployWizardReq(BaseModel):
    token_id: str
    name: str = Field(min_length=1, max_length=60)
    region: str
    size: str
    image: str | None = None
    ssh_keys: list[str] | None = None
    windows_version: str
    rdp_password: str = Field(min_length=6, max_length=64)
    rdp_port: int = 3389

    @field_validator("rdp_port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("RDP port must be between 1 and 65535")
        return value


class ReinstallReq(BaseModel):
    token_id: str
    windows_version: str


@router.post("/deploy-windows")
async def deploy_windows(payload: DeployWizardReq, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await wizard_service.deploy_windows(
        db=db,
        user_id=user.user_id,
        token_id=payload.token_id,
        name=payload.name,
        region=payload.region,
        size=payload.size,
        ssh_keys=payload.ssh_keys,
        windows_version=payload.windows_version,
        rdp_password=payload.rdp_password,
        rdp_port=payload.rdp_port,
    )


@router.get("/progress/{droplet_id}")
async def install_progress(droplet_id: int, token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await wizard_service.get_install_progress(db, user.user_id, token_id, droplet_id)


@router.post("/reinstall/{droplet_id}")
async def reinstall_windows(
    droplet_id: int,
    payload: ReinstallReq,
    user=Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    return await wizard_service.reinstall_windows(
        db=db,
        user_id=user.user_id,
        token_id=payload.token_id,
        droplet_id=droplet_id,
        windows_version=payload.windows_version,
    )


@router.get("/jobs")
async def recent_jobs(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await wizard_service.list_recent_jobs(db, user.user_id)
