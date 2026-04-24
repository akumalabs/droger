from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.services.auth_service import get_user_from_request
from app.models import User


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    return await get_user_from_request(request, db)
