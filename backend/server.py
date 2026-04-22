from fastapi import FastAPI, APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
import httpx
from urllib.parse import urlencode

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

DO_API_BASE = "https://api.digitalocean.com/v2"

app = FastAPI(title="Droplet Manager API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("droplet-manager")


# ------------------------------- Helpers ------------------------------- #
def _require_token(x_do_token: Optional[str]) -> str:
    if not x_do_token or not x_do_token.strip():
        raise HTTPException(status_code=401, detail="Missing DigitalOcean API token (X-DO-Token header).")
    return x_do_token.strip()


async def _do_request(
    method: str,
    path: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{DO_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, headers=headers, params=params, json=json_body)
    if resp.status_code == 204:
        return {"ok": True}
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    if resp.status_code >= 400:
        msg = data.get("message") if isinstance(data, dict) else str(data)
        raise HTTPException(status_code=resp.status_code, detail=msg or "DigitalOcean API error")
    return data


# ------------------------------- Models -------------------------------- #
class CreateDropletRequest(BaseModel):
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


class PowerActionRequest(BaseModel):
    action_type: str  # power_on, power_off, shutdown, reboot, power_cycle, rebuild, enable_backups, disable_backups
    image: Optional[str] = None  # for rebuild


class SnapshotCreateRequest(BaseModel):
    name: str


class WindowsScriptRequest(BaseModel):
    version: str  # key from WINDOWS_VERSIONS
    password: str
    rdp_port: int = 3389


WINDOWS_VERSIONS: Dict[str, Dict[str, str]] = {
    "win10pro": {
        "label": "Windows 10 Pro",
        "image_name": "Windows 10 Pro",
        "iso": "https://fafda.to/d/fuxscqu93mnn?v=Vp6_aNhhYS79d6Q2fRUQOaZ2wJct9EsnrCVq8-GHjGrgS_TRciyd4VFeKYHBGOZp6xO42x8i24hJMAaLHJrTUeGrryy8jOn20HSvsc2eKb_jNhnIumZidL5VuQVky5GEXM5VWvU7X_5Wn2_Iu4Nk6oigtevIUwBAhMEvfq7EchuUy2b_mO9Ry0cK9xc7dlys-PIUHmjsQjwG5MGoVxO8Ip12ASnT02V0oCb0hotUsQR4wtk4wGe3h5mwsvV2r5J4Jg82U_kGnFqmQzxJGog35Ty_opN9mFUIYNzRkVw78dPM2OPoamqlRp1oqgFMut4e8VC8sYz--cOTr0RNUkY",
    },
    "win11pro": {
        "label": "Windows 11 Pro",
        "image_name": "Windows 11 Pro",
        "iso": "https://dl.zerofs.link/dl/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJidWNrZXQiOiJhc3NldHMtYW1zIiwia2V5Ijoib05xNVlUcml4ekJlZGtoRzJxZXl2cS80M2I3YzZkMDRmY2Q0ZDNhOGJjZjQ1NTA3MTlhOTI4ZiIsImZpbGVuYW1lIjoiZW4tdXNfd2luZG93c18xMV9jb25zdW1lcl9lZGl0aW9uc192ZXJzaW9uXzI1aDJfdXBkYXRlZF9tYXJjaF8yMDI2X3g2NF9kdmRfYTFjZjZjMzYuaXNvIiwiYnVja2V0X2NvZGUiOiJldSIsImVuZHBvaW50IjoiczMuZXUtY2VudHJhbC0wMDMuYmFja2JsYXplYjIuY29tIiwiZXhwIjoxNzc0OTgxNjYzLCJrZXlfYjY0IjoicURpemVNSENxQllDUEdPZDN3NFZXallIbGhVU3dXZ1M3YXkrb1dISWJKVT0iLCJrZXlfbWQ1IjoiNzg4STdydzl6ZTQwQnNHKzZCYzZGZz09In0.MOY-rYGRk9HxowAFD3DuDXl9XesgMai4yYOgsNv5h4Q",
    },
    "win2012": {
        "label": "Windows Server 2012 R2 DC",
        "image_name": "Windows Server 2012 R2 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195443",
    },
    "win2016": {
        "label": "Windows Server 2016 DC",
        "image_name": "Windows Server 2016 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195174",
    },
    "win2019": {
        "label": "Windows Server 2019 DC",
        "image_name": "Windows Server 2019 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195167",
    },
    "win2022": {
        "label": "Windows Server 2022 DC",
        "image_name": "Windows Server 2022 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2195280",
    },
    "win2025": {
        "label": "Windows Server 2025 DC",
        "image_name": "Windows Server 2025 SERVERDATACENTER",
        "iso": "https://go.microsoft.com/fwlink/p/?LinkID=2293312",
    },
    "win10ltsc": {
        "label": "Windows 10 LTSC (DD template)",
        "image_name": "Windows 10 LTSC",
        "iso": "https://cp.akumalabs.com/storage/images/win-10-ltsc.xz",
        "mode": "dd",
    },
}


def build_windows_command(version: str, password: str, rdp_port: int) -> str:
    meta = WINDOWS_VERSIONS.get(version)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unknown Windows version: {version}")

    # sanitize password for single-quote bash safety
    safe_pw = password.replace("'", "'\\''")
    safe_img = meta["image_name"].replace("'", "'\\''")
    iso = meta["iso"]

    if meta.get("mode") == "dd":
        cmd = (
            "curl -O https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh || "
            "wget -O reinstall.sh https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh && "
            f"bash reinstall.sh dd --img '{iso}' --password '{safe_pw}' --rdp-port {int(rdp_port)} --allow-ping && "
            "reboot"
        )
    else:
        cmd = (
            "curl -O https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh || "
            "wget -O reinstall.sh https://raw.githubusercontent.com/akumalabs/reinstall/main/reinstall.sh && "
            f"bash reinstall.sh windows --image-name='{safe_img}' --iso='{iso}' "
            f"--password '{safe_pw}' --rdp-port {int(rdp_port)} --allow-ping && "
            "reboot"
        )
    return cmd


# ------------------------------- Routes -------------------------------- #
@api_router.get("/")
async def root():
    return {"service": "Droplet Manager API", "status": "ok"}


@api_router.get("/do/windows-versions")
async def list_windows_versions():
    return {
        "versions": [
            {"key": k, "label": v["label"], "mode": v.get("mode", "windows")}
            for k, v in WINDOWS_VERSIONS.items()
        ]
    }


@api_router.post("/do/windows-script")
async def windows_script(req: WindowsScriptRequest):
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if not (1 <= req.rdp_port <= 65535):
        raise HTTPException(status_code=400, detail="RDP port must be between 1 and 65535.")
    cmd = build_windows_command(req.version, req.password, req.rdp_port)
    return {"command": cmd, "version": req.version, "rdp_port": req.rdp_port}


@api_router.get("/do/account")
async def get_account(x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", "/account", token)
    return data


@api_router.get("/do/droplets")
async def list_droplets(x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", "/droplets", token, params={"per_page": 200})
    return data


@api_router.get("/do/droplets/{droplet_id}")
async def get_droplet(droplet_id: int, x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", f"/droplets/{droplet_id}", token)
    return data


@api_router.post("/do/droplets")
async def create_droplet(req: CreateDropletRequest, x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    body = req.model_dump(exclude_none=True)
    data = await _do_request("POST", "/droplets", token, json_body=body)
    return data


@api_router.delete("/do/droplets/{droplet_id}")
async def delete_droplet(droplet_id: int, x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("DELETE", f"/droplets/{droplet_id}", token)
    return data


ALLOWED_ACTIONS = {
    "power_on", "power_off", "shutdown", "reboot", "power_cycle",
    "rebuild", "enable_ipv6", "enable_backups", "disable_backups", "password_reset",
}


@api_router.post("/do/droplets/{droplet_id}/actions")
async def droplet_action(
    droplet_id: int,
    req: PowerActionRequest,
    x_do_token: Optional[str] = Header(None, alias="X-DO-Token"),
):
    token = _require_token(x_do_token)
    if req.action_type not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {req.action_type}")
    body: Dict[str, Any] = {"type": req.action_type}
    if req.action_type == "rebuild":
        if not req.image:
            raise HTTPException(status_code=400, detail="image is required for rebuild")
        body["image"] = req.image
    data = await _do_request("POST", f"/droplets/{droplet_id}/actions", token, json_body=body)
    return data


@api_router.get("/do/droplets/{droplet_id}/snapshots")
async def list_droplet_snapshots(droplet_id: int, x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", f"/droplets/{droplet_id}/snapshots", token)
    return data


@api_router.post("/do/droplets/{droplet_id}/snapshot")
async def create_droplet_snapshot(
    droplet_id: int,
    req: SnapshotCreateRequest,
    x_do_token: Optional[str] = Header(None, alias="X-DO-Token"),
):
    token = _require_token(x_do_token)
    body = {"type": "snapshot", "name": req.name}
    data = await _do_request("POST", f"/droplets/{droplet_id}/actions", token, json_body=body)
    return data


@api_router.delete("/do/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("DELETE", f"/snapshots/{snapshot_id}", token)
    return data


@api_router.get("/do/regions")
async def list_regions(x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", "/regions", token, params={"per_page": 200})
    return data


@api_router.get("/do/sizes")
async def list_sizes(x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", "/sizes", token, params={"per_page": 200})
    return data


@api_router.get("/do/images")
async def list_images(
    type: str = "distribution",
    x_do_token: Optional[str] = Header(None, alias="X-DO-Token"),
):
    token = _require_token(x_do_token)
    data = await _do_request("GET", "/images", token, params={"type": type, "per_page": 200})
    return data


@api_router.get("/do/ssh_keys")
async def list_ssh_keys(x_do_token: Optional[str] = Header(None, alias="X-DO-Token")):
    token = _require_token(x_do_token)
    data = await _do_request("GET", "/account/keys", token, params={"per_page": 200})
    return data


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
