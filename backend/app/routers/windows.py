from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from app.core.deps import current_user
from app.services.windows import WINDOWS_VERSIONS, build_windows_command

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
    command = build_windows_command(payload.version, payload.password, payload.rdp_port)
    return {"command": command, "version": payload.version, "rdp_port": payload.rdp_port}
