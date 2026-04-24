from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.deps import current_user
from app.services import template_service

router = APIRouter(prefix="/api/templates", tags=["templates"])


class CreateTemplateReq(BaseModel):
    token_id: str
    snapshot_id: int
    label: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_droplet_id: int | None = None
    snapshot_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def normalize_legacy_fields(self):
        if not self.label and self.name:
            self.label = self.name
        if self.notes is None and self.description is not None:
            self.notes = self.description
        if not self.label:
            raise ValueError("label is required")
        return self


class SyncTemplateReq(BaseModel):
    token_id: str


class DeployTemplateReq(BaseModel):
    token_id: str
    name: str = Field(min_length=1, max_length=64)
    region: str
    size: str
    ssh_keys: list[str] | None = None


@router.get("")
async def list_templates(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await template_service.list_templates(db, user.user_id)


@router.post("/from-snapshot")
async def create_from_snapshot(payload: CreateTemplateReq, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await template_service.create_template_from_snapshot(
        db=db,
        user_id=user.user_id,
        token_id=payload.token_id,
        snapshot_id=payload.snapshot_id,
        label=payload.label or "",
        notes=payload.notes,
        source_droplet_id=payload.source_droplet_id,
        snapshot_name=payload.snapshot_name,
    )


@router.post("/{template_id}/sync")
async def sync_template(template_id: str, payload: SyncTemplateReq, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await template_service.sync_template_to_token(db, user.user_id, template_id, payload.token_id)


@router.post("/{template_id}/deploy")
async def deploy_template(template_id: str, payload: DeployTemplateReq, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await template_service.deploy_from_template(
        db=db,
        user_id=user.user_id,
        template_id=template_id,
        target_token_id=payload.token_id,
        name=payload.name,
        region=payload.region,
        size=payload.size,
        ssh_keys=payload.ssh_keys,
    )


@router.delete("/{template_id}")
async def delete_template(template_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await template_service.delete_template(db, user.user_id, template_id)
