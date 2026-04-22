from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field, field_validator

import auth as auth_mod
import crypto_utils as cu

DO_API_BASE = "https://api.digitalocean.com/v2"

# --- DB -----------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# --- App ----------------------------------------------------------------
app = FastAPI(title="Droplet Manager API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("droplet-manager")


# ========================= AUTH ========================================
class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: Optional[str] = None


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class SessionReq(BaseModel):
    session_id: str


async def current_user(request: Request) -> dict:
    return await auth_mod.get_current_user(request, db)


@api.post("/auth/register")
async def register(payload: RegisterReq, request: Request, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = {
        "user_id": auth_mod.new_user_id(),
        "email": email,
        "name": payload.name or email.split("@")[0],
        "password_hash": auth_mod.hash_password(payload.password),
        "auth_provider": "email",
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    access = auth_mod.create_access_token(user_doc["user_id"], email)
    refresh = auth_mod.create_refresh_token(user_doc["user_id"])
    auth_mod.set_auth_cookies(response, access, refresh)
    user_doc.pop("password_hash", None)
    user_doc.pop("_id", None)
    return user_doc


@api.post("/auth/login")
async def login(payload: LoginReq, request: Request, response: Response):
    email = payload.email.lower().strip()
    identifier = f"email:{email}"
    await auth_mod.check_lockout(db, identifier)

    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        await auth_mod.record_failed_attempt(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not auth_mod.verify_password(payload.password, user["password_hash"]):
        await auth_mod.record_failed_attempt(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await auth_mod.clear_attempts(db, identifier)
    access = auth_mod.create_access_token(user["user_id"], email)
    refresh = auth_mod.create_refresh_token(user["user_id"])
    auth_mod.set_auth_cookies(response, access, refresh)
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "role": user.get("role", "user"),
        "auth_provider": user.get("auth_provider", "email"),
    }


@api.post("/auth/session")
async def google_session_exchange(payload: SessionReq, response: Response):
    """Emergent Google OAuth: frontend sends session_id from URL fragment."""
    data = await auth_mod.exchange_emergent_session(payload.session_id)
    email = data.get("email", "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="No email returned by provider")

    user = await db.users.find_one({"email": email})
    if not user:
        user = {
            "user_id": auth_mod.new_user_id(),
            "email": email,
            "name": data.get("name") or email.split("@")[0],
            "picture": data.get("picture"),
            "auth_provider": "google",
            "role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
    else:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "name": data.get("name") or user.get("name"),
                "picture": data.get("picture") or user.get("picture"),
                "auth_provider": "both" if user.get("auth_provider") == "email" else "google",
            }},
        )
        user = await db.users.find_one({"user_id": user["user_id"]})

    # Store session
    session_token = auth_mod.new_session_token()
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    auth_mod.set_session_cookie(response, session_token)
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "picture": user.get("picture"),
        "role": user.get("role", "user"),
        "auth_provider": user.get("auth_provider"),
    }


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return user


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    # Invalidate Emergent session if present
    st = request.cookies.get("session_token")
    if st:
        await db.user_sessions.delete_one({"session_token": st})
    auth_mod.clear_auth_cookies(response)
    return {"ok": True}


@api.post("/auth/refresh")
async def refresh_token_endpoint(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = auth_mod.decode_token(rt)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    access = auth_mod.create_access_token(user["user_id"], user["email"])
    response.set_cookie(
        "access_token", access, httponly=True, secure=True, samesite="none",
        max_age=auth_mod.ACCESS_TTL_MIN * 60, path="/",
    )
    return {"ok": True}


# ========================= DO TOKENS VAULT =============================
class AddTokenReq(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    token: str = Field(min_length=10)


class RenameTokenReq(BaseModel):
    name: str = Field(min_length=1, max_length=50)


async def _validate_do_token(do_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(
            f"{DO_API_BASE}/account",
            headers={"Authorization": f"Bearer {do_token}"},
        )
    if r.status_code == 401:
        raise HTTPException(status_code=400, detail="DigitalOcean rejected this token")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"DO error: {r.text[:120]}")
    return r.json().get("account", {})


def _public_token(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "name": doc["name"],
        "do_email": doc.get("do_email"),
        "do_uuid": doc.get("do_uuid"),
        "droplet_limit": doc.get("droplet_limit"),
        "created_at": doc.get("created_at"),
        "last_used_at": doc.get("last_used_at"),
    }


@api.get("/do-tokens")
async def list_tokens(user: dict = Depends(current_user)):
    docs = await db.do_tokens.find({"user_id": user["user_id"]}, {"_id": 0, "token_encrypted": 0}).to_list(200)
    docs.sort(key=lambda d: d.get("created_at", ""))
    return {"tokens": [_public_token(d) for d in docs]}


@api.post("/do-tokens")
async def add_token(payload: AddTokenReq, user: dict = Depends(current_user)):
    account = await _validate_do_token(payload.token.strip())
    doc = {
        "id": f"tok_{auth_mod.secrets.token_urlsafe(12)}",
        "user_id": user["user_id"],
        "name": payload.name.strip(),
        "token_encrypted": cu.encrypt(payload.token.strip()),
        "do_email": account.get("email"),
        "do_uuid": account.get("uuid"),
        "droplet_limit": account.get("droplet_limit"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.do_tokens.insert_one(doc)
    return _public_token(doc)


@api.patch("/do-tokens/{token_id}")
async def rename_token(token_id: str, payload: RenameTokenReq, user: dict = Depends(current_user)):
    res = await db.do_tokens.update_one(
        {"id": token_id, "user_id": user["user_id"]},
        {"$set": {"name": payload.name.strip()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    doc = await db.do_tokens.find_one({"id": token_id}, {"_id": 0, "token_encrypted": 0})
    return _public_token(doc)


@api.delete("/do-tokens/{token_id}")
async def delete_token(token_id: str, user: dict = Depends(current_user)):
    res = await db.do_tokens.delete_one({"id": token_id, "user_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"ok": True}


async def _resolve_token(user_id: str, token_id: str) -> str:
    doc = await db.do_tokens.find_one({"id": token_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="DO token not found")
    await db.do_tokens.update_one(
        {"id": token_id},
        {"$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}},
    )
    return cu.decrypt(doc["token_encrypted"])


# ========================= DO API PROXY ================================
async def _do(method: str, path: str, token: str, params=None, json_body=None) -> dict:
    url = f"{DO_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.request(method, url, headers=headers, params=params, json=json_body)
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
    return await _resolve_token(user["user_id"], token_id)


@api.get("/do/account")
async def do_account(token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", "/account", t)


@api.get("/do/droplets")
async def do_list_droplets(token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", "/droplets", t, params={"per_page": 200})


@api.get("/do/droplets/{droplet_id}")
async def do_get_droplet(droplet_id: int, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", f"/droplets/{droplet_id}", t)


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


@api.post("/do/droplets")
async def do_create_droplet(payload: CreateDropletReq, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("POST", "/droplets", t, json_body=payload.model_dump(exclude_none=True))


@api.delete("/do/droplets/{droplet_id}")
async def do_delete_droplet(droplet_id: int, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("DELETE", f"/droplets/{droplet_id}", t)


ALLOWED_ACTIONS = {
    "power_on", "power_off", "shutdown", "reboot", "power_cycle",
    "rebuild", "enable_ipv6", "enable_backups", "disable_backups", "password_reset",
}


class DropletActionReq(BaseModel):
    action_type: str
    image: Optional[str] = None


@api.post("/do/droplets/{droplet_id}/actions")
async def do_droplet_action(droplet_id: int, payload: DropletActionReq, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    if payload.action_type not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {payload.action_type}")
    body: Dict[str, Any] = {"type": payload.action_type}
    if payload.action_type == "rebuild":
        if not payload.image:
            raise HTTPException(status_code=400, detail="image is required for rebuild")
        body["image"] = payload.image
    return await _do("POST", f"/droplets/{droplet_id}/actions", t, json_body=body)


@api.get("/do/droplets/{droplet_id}/snapshots")
async def do_droplet_snapshots(droplet_id: int, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", f"/droplets/{droplet_id}/snapshots", t)


class SnapshotReq(BaseModel):
    name: str = Field(min_length=1)


@api.post("/do/droplets/{droplet_id}/snapshot")
async def do_droplet_snapshot(droplet_id: int, payload: SnapshotReq, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("POST", f"/droplets/{droplet_id}/actions", t, json_body={"type": "snapshot", "name": payload.name})


@api.delete("/do/snapshots/{snapshot_id}")
async def do_delete_snapshot(snapshot_id: str, token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("DELETE", f"/snapshots/{snapshot_id}", t)


@api.get("/do/regions")
async def do_regions(token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", "/regions", t, params={"per_page": 200})


@api.get("/do/sizes")
async def do_sizes(token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", "/sizes", t, params={"per_page": 200})


@api.get("/do/images")
async def do_images(token_id: str, type: str = "distribution", user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", "/images", t, params={"type": type, "per_page": 200})


@api.get("/do/ssh_keys")
async def do_ssh_keys(token_id: str, user: dict = Depends(current_user)):
    t = await _tok(user, token_id)
    return await _do("GET", "/account/keys", t, params={"per_page": 200})


# ========================= WINDOWS SCRIPT ==============================
WINDOWS_VERSIONS: Dict[str, Dict[str, str]] = {
    "win10pro": {"label": "Windows 10 Pro", "image_name": "Windows 10 Pro",
                 "iso": "https://fafda.to/d/fuxscqu93mnn?v=Vp6_aNhhYS79d6Q2fRUQOaZ2wJct9EsnrCVq8-GHjGrgS_TRciyd4VFeKYHBGOZp6xO42x8i24hJMAaLHJrTUeGrryy8jOn20HSvsc2eKb_jNhnIumZidL5VuQVky5GEXM5VWvU7X_5Wn2_Iu4Nk6oigtevIUwBAhMEvfq7EchuUy2b_mO9Ry0cK9xc7dlys-PIUHmjsQjwG5MGoVxO8Ip12ASnT02V0oCb0hotUsQR4wtk4wGe3h5mwsvV2r5J4Jg82U_kGnFqmQzxJGog35Ty_opN9mFUIYNzRkVw78dPM2OPoamqlRp1oqgFMut4e8VC8sYz--cOTr0RNUkY"},
    "win11pro": {"label": "Windows 11 Pro", "image_name": "Windows 11 Pro",
                 "iso": "https://dl.zerofs.link/dl/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJidWNrZXQiOiJhc3NldHMtYW1zIiwia2V5Ijoib05xNVlUcml4ekJlZGtoRzJxZXl2cS80M2I3YzZkMDRmY2Q0ZDNhOGJjZjQ1NTA3MTlhOTI4ZiIsImZpbGVuYW1lIjoiZW4tdXNfd2luZG93c18xMV9jb25zdW1lcl9lZGl0aW9uc192ZXJzaW9uXzI1aDJfdXBkYXRlZF9tYXJjaF8yMDI2X3g2NF9kdmRfYTFjZjZjMzYuaXNvIiwiYnVja2V0X2NvZGUiOiJldSIsImVuZHBvaW50IjoiczMuZXUtY2VudHJhbC0wMDMuYmFja2JsYXplYjIuY29tIiwiZXhwIjoxNzc0OTgxNjYzLCJrZXlfYjY0IjoicURpemVNSENxQllDUEdPZDN3NFZXallIbGhVU3dXZ1M3YXkrb1dISWJKVT0iLCJrZXlfbWQ1IjoiNzg4STdydzl6ZTQwQnNHKzZCYzZGZz09In0.MOY-rYGRk9HxowAFD3DuDXl9XesgMai4yYOgsNv5h4Q"},
    "win2012": {"label": "Windows Server 2012 R2 DC", "image_name": "Windows Server 2012 R2 SERVERDATACENTER", "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195443"},
    "win2016": {"label": "Windows Server 2016 DC", "image_name": "Windows Server 2016 SERVERDATACENTER", "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195174"},
    "win2019": {"label": "Windows Server 2019 DC", "image_name": "Windows Server 2019 SERVERDATACENTER", "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195167"},
    "win2022": {"label": "Windows Server 2022 DC", "image_name": "Windows Server 2022 SERVERDATACENTER", "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195280"},
    "win2025": {"label": "Windows Server 2025 DC", "image_name": "Windows Server 2025 SERVERDATACENTER", "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2293312"},
    "win10ltsc": {"label": "Windows 10 LTSC (DD template)", "image_name": "Windows 10 LTSC",
                  "iso": "https://cp.akumalabs.com/storage/images/win-10-ltsc.xz", "mode": "dd"},
}


class WindowsScriptReq(BaseModel):
    version: str
    password: str = Field(min_length=6, max_length=64)
    rdp_port: int = 3389

    @field_validator("rdp_port")
    @classmethod
    def _port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("RDP port must be between 1 and 65535")
        return v


def _build_windows_command(version: str, password: str, rdp_port: int) -> str:
    meta = WINDOWS_VERSIONS.get(version)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unknown Windows version: {version}")
    safe_pw = password.replace("'", "'\\''")
    safe_img = meta["image_name"].replace("'", "'\\''")
    iso = meta["iso"]
    base = (
        "curl -O https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh || "
        "wget -O reinstall.sh https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh && "
    )
    if meta.get("mode") == "dd":
        return base + f"bash reinstall.sh dd --img '{iso}' --password '{safe_pw}' --rdp-port {int(rdp_port)} --allow-ping && reboot"
    return base + (
        f"bash reinstall.sh windows --image-name='{safe_img}' --iso='{iso}' "
        f"--password '{safe_pw}' --rdp-port {int(rdp_port)} --allow-ping && reboot"
    )


@api.get("/do/windows-versions")
async def windows_versions():
    return {"versions": [
        {"key": k, "label": v["label"], "mode": v.get("mode", "windows")}
        for k, v in WINDOWS_VERSIONS.items()
    ]}


@api.post("/do/windows-script")
async def windows_script(payload: WindowsScriptReq, user: dict = Depends(current_user)):
    cmd = _build_windows_command(payload.version, payload.password, payload.rdp_port)
    return {"command": cmd, "version": payload.version, "rdp_port": payload.rdp_port}


# ========================= DEPLOY WIZARD ===============================
class DeployWizardReq(BaseModel):
    token_id: str
    name: str = Field(min_length=1, max_length=60)
    region: str
    size: str
    image: str  # Linux slug, e.g. "ubuntu-22-04-x64"
    ssh_keys: Optional[List[str]] = None
    windows_version: str
    rdp_password: str = Field(min_length=6, max_length=64)
    rdp_port: int = 3389

    @field_validator("rdp_port")
    @classmethod
    def _port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("RDP port must be between 1 and 65535")
        return v


@api.post("/wizard/deploy-windows")
async def deploy_windows(payload: DeployWizardReq, user: dict = Depends(current_user)):
    t = await _resolve_token(user["user_id"], payload.token_id)
    body = {
        "name": payload.name,
        "region": payload.region,
        "size": payload.size,
        "image": payload.image,
        "backups": False,
        "ipv6": False,
        "monitoring": True,
        "tags": ["droplet-manager", "windows-pending"],
    }
    if payload.ssh_keys:
        body["ssh_keys"] = payload.ssh_keys
    res = await _do("POST", "/droplets", t, json_body=body)
    droplet = res.get("droplet", {})
    command = _build_windows_command(payload.windows_version, payload.rdp_password, payload.rdp_port)
    # persist wizard context for UI
    await db.wizard_jobs.insert_one({
        "job_id": f"job_{auth_mod.secrets.token_urlsafe(12)}",
        "user_id": user["user_id"],
        "token_id": payload.token_id,
        "droplet_id": droplet.get("id"),
        "windows_version": payload.windows_version,
        "rdp_port": payload.rdp_port,
        "command": command,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"droplet": droplet, "command": command}


# ========================= STARTUP =====================================
@app.on_event("startup")
async def _startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.user_sessions.create_index("user_id")
    await db.login_attempts.create_index("identifier")
    await db.do_tokens.create_index([("user_id", 1), ("id", 1)], unique=True)

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
                "role": "admin",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Seeded admin user {admin_email}")
        elif not auth_mod.verify_password(admin_password, existing.get("password_hash", "")):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": auth_mod.hash_password(admin_password)}},
            )
            logger.info(f"Updated admin password for {admin_email}")


@app.on_event("shutdown")
async def _shutdown():
    client.close()


# ========================= CORS ========================================
app.include_router(api)

allowed = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if frontend_url and frontend_url not in allowed and "*" not in allowed:
    allowed.append(frontend_url)

# If we need credentials, we cannot use wildcard origin. Auto-switch:
if allowed == ["*"]:
    # Fall back to frontend URL + localhost dev
    allowed = [frontend_url, "http://localhost:3000"] if frontend_url else ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
