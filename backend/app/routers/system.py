from fastapi import APIRouter, Depends
from app.core.deps import current_user
from app.services import update_service

router = APIRouter(prefix="/api/system", tags=["system"])


def _ensure_admin(user) -> None:
    if getattr(user, "role", None) != "admin":
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/update")
async def update_status(user=Depends(current_user)):
    _ensure_admin(user)
    return update_service.get_update_status()


@router.post("/update")
async def apply_update(user=Depends(current_user)):
    _ensure_admin(user)
    return update_service.apply_update()
