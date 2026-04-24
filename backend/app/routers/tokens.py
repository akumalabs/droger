from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.core.db import get_db
from app.core.deps import current_user
from app.services import token_service

router = APIRouter(prefix="/api/do-tokens", tags=["do-tokens"])


class AddTokenReq(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    token: str = Field(min_length=10)


class RenameTokenReq(BaseModel):
    name: str = Field(min_length=1, max_length=50)


@router.get("")
async def list_tokens(user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await token_service.list_tokens(db, user.user_id)


@router.post("")
async def add_token(payload: AddTokenReq, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await token_service.add_token(db, user.user_id, payload.name, payload.token)


@router.patch("/{token_id}")
async def rename_token(token_id: str, payload: RenameTokenReq, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await token_service.rename_token(db, user.user_id, token_id, payload.name)


@router.delete("/{token_id}")
async def delete_token(token_id: str, user=Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await token_service.delete_token(db, user.user_id, token_id)
