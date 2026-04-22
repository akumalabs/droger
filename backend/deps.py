"""FastAPI dependencies shared across routers."""
from fastapi import Request
import auth as auth_mod
from db import db


async def current_user(request: Request) -> dict:
    return await auth_mod.get_current_user(request, db)
