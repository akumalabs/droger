from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.core.config import get_settings
from app.core.db import dispose_engine, get_engine, get_session_factory
from app.core.redis import close_redis, init_redis
from app.core.security import hash_password, verify_password, new_user_id
from app.models import Base, User
from app.routers import auth_router, do_proxy_router, tokens_router, windows_router, wizard_router, system_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_redis()
    if settings.admin_email and settings.admin_password:
        session_factory = get_session_factory()
        async with session_factory() as session:
            existing = await session.scalar(select(User).where(User.email == settings.admin_email))
            if not existing:
                session.add(
                    User(
                        user_id=new_user_id(),
                        email=settings.admin_email,
                        name="Admin",
                        password_hash=hash_password(settings.admin_password),
                        auth_provider="email",
                        email_verified=True,
                        role="admin",
                        created_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()
            elif not verify_password(settings.admin_password, existing.password_hash or ""):
                existing.password_hash = hash_password(settings.admin_password)
                existing.email_verified = True
                await session.commit()
    yield
    await close_redis()
    await dispose_engine()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

meta_router = APIRouter(prefix="/api")


@meta_router.get("/")
async def root():
    return {"service": settings.app_name, "status": "ok"}


@meta_router.get("/health")
async def health():
    return {"ok": True}


allowed_origins = settings.cors_origins
if settings.frontend_url and settings.frontend_url not in allowed_origins:
    allowed_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta_router)
app.include_router(auth_router)
app.include_router(tokens_router)
app.include_router(do_proxy_router)
app.include_router(windows_router)
app.include_router(wizard_router)
app.include_router(system_router)
