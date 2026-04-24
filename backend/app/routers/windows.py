from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from app.core.deps import current_user
from app.services.windows import WINDOWS_VERSIONS

router = APIRouter(prefix="/api/do", tags=["windows"])


class WindowsScriptReq(BaseModel):
    version: str
    password: str = Field(min_length=6, max_length=64)
    rdp_port: int = 3389

    @field_validator("rdp_port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("RDP port must be between 1 and 65535")
        return value


@router.get("/windows-versions")
async def windows_versions():
    return {
        "versions": [
            {"key": key, "label": value["label"], "mode": value.get("mode", "windows")}
            for key, value in WINDOWS_VERSIONS.items()
        ]
    }


@router.post("/windows-script")
async def windows_script(payload: WindowsScriptReq, user=Depends(current_user)):
    raise HTTPException(status_code=403, detail="Manual Windows install command is disabled. Use deploy wizard auto-install.")
