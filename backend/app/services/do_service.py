from typing import Any
import httpx
from fastapi import HTTPException

DO_API_BASE = "https://api.digitalocean.com/v2"


async def do_request(
    method: str,
    path: str,
    token: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, f"{DO_API_BASE}{path}", headers=headers, params=params, json=json_body)
    if response.status_code == 204:
        return {"ok": True}
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        detail = data.get("message") if isinstance(data, dict) else str(data)
        raise HTTPException(status_code=response.status_code, detail=detail)
    return data
