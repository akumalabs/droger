"""App entrypoint: CORS, startup, router includes."""
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

import auth as auth_mod
from db import db, close as db_close
from routers.auth_routes import router as auth_router
from routers.tokens import router as tokens_router
from routers.do_proxy import router as do_proxy_router
from routers.windows import router as windows_router
from routers.wizard import router as wizard_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("droplet-manager")

app = FastAPI(title="Droplet Manager API")

# health ping
meta_router = APIRouter(prefix="/api")


@meta_router.get("/")
async def root():
    return {"service": "Droplet Manager API", "status": "ok"}


app.include_router(meta_router)
app.include_router(auth_router)
app.include_router(tokens_router)
app.include_router(do_proxy_router)
app.include_router(windows_router)
app.include_router(wizard_router)


# ---------- Startup ---------- #
@app.on_event("startup")
async def _startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("user_id")
    # TTL: expire login_attempts rows 15 min after last_attempt
    await db.login_attempts.create_index(
        "last_attempt", expireAfterSeconds=auth_mod.LOCKOUT_MINUTES * 60,
        name="last_attempt_ttl",
    )
    await db.login_attempts.create_index("identifier")
    # TTL: expire verification + reset tokens at their own expires_at
    await db.email_verification_tokens.create_index(
        "expires_at", expireAfterSeconds=0, name="verify_ttl",
    )
    await db.email_verification_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index(
        "expires_at", expireAfterSeconds=0, name="reset_ttl",
    )
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.do_tokens.create_index([("user_id", 1), ("id", 1)], unique=True)

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "").lower().strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    if admin_email and admin_password:
        existing = await db.users.find_one({"email": admin_email})
        if not existing:
            await db.users.insert_one({
                "user_id": auth_mod.new_user_id(),
                "email": admin_email,
                "name": "Admin",
                "password_hash": auth_mod.hash_password(admin_password),
                "auth_provider": "email",
                "email_verified": True,
                "role": "admin",
                "created_at": datetime.now(timezone.utc),
            })
            logger.info(f"Seeded admin user {admin_email}")
        elif not auth_mod.verify_password(admin_password, existing.get("password_hash", "")):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": auth_mod.hash_password(admin_password), "email_verified": True}},
            )
            logger.info(f"Updated admin password for {admin_email}")


@app.on_event("shutdown")
async def _shutdown():
    db_close()


# ---------- CORS ---------- #
allowed = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if frontend_url and frontend_url not in allowed and "*" not in allowed:
    allowed.append(frontend_url)
if allowed == ["*"]:
    allowed = [frontend_url, "http://localhost:3000"] if frontend_url else ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
