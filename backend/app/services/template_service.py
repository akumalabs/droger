from datetime import datetime, timezone
import asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core import crypto, security
from app.models import DOToken, SnapshotTemplate, SnapshotTemplateAccountState
from . import do_service

ACCOUNT_STATUS_PENDING = "pending"
ACCOUNT_STATUS_TRANSFERRING = "transferring"
ACCOUNT_STATUS_AVAILABLE = "available"
ACCOUNT_STATUS_ERROR = "error"

TEMPLATE_STATUS_AVAILABLE = "available"
TEMPLATE_STATUS_TRANSFERRING = "transferring"
TEMPLATE_STATUS_ERROR = "error"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_value(row: DOToken) -> str:
    return crypto.decrypt(row.token_encrypted)


def _int_or_none(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


async def _token_row(db: AsyncSession, user_id: str, token_id: str) -> DOToken:
    row = await db.scalar(select(DOToken).where(DOToken.user_id == user_id, DOToken.token_id == token_id))
    if not row:
        raise HTTPException(status_code=404, detail="DO token not found")
    return row


async def _token_rows(db: AsyncSession, user_id: str) -> list[DOToken]:
    rows = await db.scalars(select(DOToken).where(DOToken.user_id == user_id).order_by(DOToken.created_at.asc()))
    return rows.all()


async def _template_row(db: AsyncSession, user_id: str, template_id: str) -> SnapshotTemplate:
    row = await db.scalar(select(SnapshotTemplate).where(SnapshotTemplate.user_id == user_id, SnapshotTemplate.template_id == template_id))
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


async def _state_row(db: AsyncSession, template_id: str, token_id: str) -> SnapshotTemplateAccountState | None:
    return await db.scalar(
        select(SnapshotTemplateAccountState).where(
            SnapshotTemplateAccountState.template_id == template_id,
            SnapshotTemplateAccountState.token_id == token_id,
        )
    )


async def _states_for_templates(
    db: AsyncSession,
    user_id: str,
    template_ids: list[str],
) -> dict[str, dict[str, SnapshotTemplateAccountState]]:
    if not template_ids:
        return {}
    rows = await db.scalars(
        select(SnapshotTemplateAccountState).where(
            SnapshotTemplateAccountState.user_id == user_id,
            SnapshotTemplateAccountState.template_id.in_(template_ids),
        )
    )
    grouped: dict[str, dict[str, SnapshotTemplateAccountState]] = {}
    for row in rows.all():
        grouped.setdefault(row.template_id, {})[row.token_id] = row
    return grouped


async def _upsert_account_state(
    db: AsyncSession,
    user_id: str,
    template_id: str,
    token: DOToken,
    status: str,
    image_id: int | None,
    last_error: str | None,
    last_synced_at: datetime | None = None,
) -> SnapshotTemplateAccountState:
    row = await _state_row(db, template_id, token.token_id)
    stamp = _now()
    if not row:
        row = SnapshotTemplateAccountState(
            template_id=template_id,
            user_id=user_id,
            token_id=token.token_id,
            account_uuid=token.do_uuid,
            status=status,
            image_id=image_id,
            last_error=last_error,
            last_synced_at=last_synced_at,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(row)
        return row

    row.account_uuid = token.do_uuid
    row.status = status
    row.image_id = image_id
    row.last_error = last_error
    if last_synced_at is not None:
        row.last_synced_at = last_synced_at
    row.updated_at = stamp
    return row


def _availability_row(
    template: SnapshotTemplate,
    token: DOToken | None,
    token_id: str,
    state: SnapshotTemplateAccountState | None,
) -> dict:
    return {
        "token_id": token_id,
        "token_name": token.name if token else None,
        "account_uuid": (state.account_uuid if state else None) or (token.do_uuid if token else None),
        "status": state.status if state else ACCOUNT_STATUS_PENDING,
        "image_id": state.image_id if state else None,
        "last_error": state.last_error if state else None,
        "last_synced_at": state.last_synced_at.isoformat() if state and state.last_synced_at else None,
        "updated_at": state.updated_at.isoformat() if state and state.updated_at else None,
        "is_owner": template.owner_token_id == token_id,
    }


def _public(
    template: SnapshotTemplate,
    tokens: list[DOToken],
    states: dict[str, SnapshotTemplateAccountState] | None = None,
) -> dict:
    token_map = {t.token_id: t for t in tokens}
    state_map = states or {}
    owner = token_map.get(template.owner_token_id)

    availability: list[dict] = []
    for token in tokens:
        availability.append(_availability_row(template, token, token.token_id, state_map.get(token.token_id)))

    for token_id, state in state_map.items():
        if token_id in token_map:
            continue
        availability.append(_availability_row(template, None, token_id, state))

    availability.sort(key=lambda row: (0 if row["is_owner"] else 1, row.get("token_name") or row["token_id"]))

    return {
        "id": template.template_id,
        "label": template.label,
        "notes": template.notes,
        "name": template.label,
        "description": template.notes,
        "snapshot_id": template.snapshot_id,
        "current_image_id": template.current_image_id,
        "source_droplet_id": template.source_droplet_id,
        "snapshot_name": template.snapshot_name,
        "owner_token_id": template.owner_token_id,
        "owner_token_name": owner.name if owner else None,
        "owner_account_uuid": template.owner_account_uuid,
        "current_token_id": template.owner_token_id,
        "current_do_uuid": template.owner_account_uuid,
        "status": template.status,
        "last_error": template.last_error,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        "last_used_at": template.last_used_at.isoformat() if template.last_used_at else None,
        "availability": availability,
    }


async def _public_for_template(db: AsyncSession, user_id: str, template: SnapshotTemplate) -> dict:
    tokens = await _token_rows(db, user_id)
    state_map = await _states_for_templates(db, user_id, [template.template_id])
    return _public(template, tokens, state_map.get(template.template_id, {}))


def _extract_transfer_id(payload: dict) -> int:
    transfer = payload.get("transfer") if isinstance(payload.get("transfer"), dict) else {}
    return _int_or_none(payload.get("transfer_id")) or _int_or_none(payload.get("id")) or _int_or_none(transfer.get("id")) or 0


def _extract_transfer_image_id(payload: dict, fallback: int) -> int:
    buckets: list[dict] = [payload]
    transfer = payload.get("transfer") if isinstance(payload.get("transfer"), dict) else None
    if transfer:
        buckets.append(transfer)

    for bucket in buckets:
        for key in ("resource_id", "image_id", "target_resource_id"):
            found = _int_or_none(bucket.get(key))
            if found:
                return found
    return fallback


async def _find_available_image_id(token_value: str, candidates: list[int | None]) -> int | None:
    seen: set[int] = set()
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            payload = await do_service.do_request("GET", f"/images/{candidate}", token_value)
        except HTTPException as exc:
            if exc.status_code == 404:
                continue
            raise
        image = payload.get("image", {})
        if not image:
            continue
        status = str(image.get("status", "")).lower()
        if status == ACCOUNT_STATUS_AVAILABLE:
            return _int_or_none(image.get("id")) or candidate
    return None


async def _wait_image_available(token: str, image_id: int, attempts: int = 30, delay_sec: float = 3.0) -> dict:
    for _ in range(attempts):
        try:
            payload = await do_service.do_request("GET", f"/images/{image_id}", token)
            image = payload.get("image", {})
            status = str(image.get("status", "")).lower()
            if status == ACCOUNT_STATUS_AVAILABLE:
                return image
            if status in {"deleted", "retired"}:
                raise HTTPException(status_code=409, detail=f"Image status is {status}")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        await asyncio.sleep(delay_sec)
    raise HTTPException(status_code=408, detail="Timed out waiting for image transfer to become available")


async def list_templates(db: AsyncSession, user_id: str) -> dict:
    rows = await db.scalars(
        select(SnapshotTemplate)
        .where(SnapshotTemplate.user_id == user_id)
        .order_by(SnapshotTemplate.created_at.desc())
    )
    templates = rows.all()
    tokens = await _token_rows(db, user_id)
    state_map = await _states_for_templates(db, user_id, [row.template_id for row in templates])
    return {"templates": [_public(row, tokens, state_map.get(row.template_id, {})) for row in templates]}


async def create_template_from_snapshot(
    db: AsyncSession,
    user_id: str,
    token_id: str,
    snapshot_id: int,
    label: str,
    notes: str | None,
    source_droplet_id: int | None,
    snapshot_name: str | None,
) -> dict:
    owner_token = await _token_row(db, user_id, token_id)
    owner_token_value = _token_value(owner_token)

    payload = await do_service.do_request("GET", f"/images/{snapshot_id}", owner_token_value)
    image = payload.get("image", {})
    if not image:
        raise HTTPException(status_code=404, detail="Snapshot image not found")
    if str(image.get("type", "")).lower() != "snapshot":
        raise HTTPException(status_code=400, detail="Only snapshot images can be saved as templates")

    clean_label = label.strip()
    if not clean_label:
        raise HTTPException(status_code=400, detail="Template label is required")

    current_image_id = _int_or_none(image.get("id")) or int(snapshot_id)
    stamp = _now()
    row = SnapshotTemplate(
        template_id=security.new_job_id().replace("job_", "tpl_", 1),
        user_id=user_id,
        label=clean_label,
        notes=(notes or "").strip() or None,
        snapshot_id=int(snapshot_id),
        current_image_id=current_image_id,
        source_droplet_id=source_droplet_id,
        snapshot_name=(snapshot_name or image.get("name") or "").strip() or None,
        owner_token_id=token_id,
        owner_account_uuid=owner_token.do_uuid,
        status=TEMPLATE_STATUS_AVAILABLE,
        last_error=None,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)

    db.add(
        SnapshotTemplateAccountState(
            template_id=row.template_id,
            user_id=user_id,
            token_id=owner_token.token_id,
            account_uuid=owner_token.do_uuid,
            status=ACCOUNT_STATUS_AVAILABLE,
            image_id=current_image_id,
            last_error=None,
            last_synced_at=stamp,
            created_at=stamp,
            updated_at=stamp,
        )
    )

    await db.commit()
    await db.refresh(row)
    return await _public_for_template(db, user_id, row)


async def delete_template(db: AsyncSession, user_id: str, template_id: str) -> dict:
    row = await _template_row(db, user_id, template_id)
    states = await db.scalars(
        select(SnapshotTemplateAccountState).where(
            SnapshotTemplateAccountState.user_id == user_id,
            SnapshotTemplateAccountState.template_id == template_id,
        )
    )
    for state in states.all():
        await db.delete(state)
    await db.delete(row)
    await db.commit()
    return {"ok": True}


async def _ensure_template_on_token(
    db: AsyncSession,
    user_id: str,
    template: SnapshotTemplate,
    target_token_id: str,
) -> tuple[SnapshotTemplate, DOToken]:
    source_token = await _token_row(db, user_id, template.owner_token_id)
    target_token = await _token_row(db, user_id, target_token_id)
    source_token_value = _token_value(source_token)
    target_token_value = _token_value(target_token)

    source_state = await _state_row(db, template.template_id, source_token.token_id)
    target_state = await _state_row(db, template.template_id, target_token.token_id)

    existing_image_id = await _find_available_image_id(
        target_token_value,
        [
            target_state.image_id if target_state else None,
            template.current_image_id,
            template.snapshot_id,
        ],
    )

    if existing_image_id is None and target_state and target_state.status == ACCOUNT_STATUS_TRANSFERRING and target_state.image_id:
        try:
            image = await _wait_image_available(target_token_value, int(target_state.image_id), attempts=10, delay_sec=2.0)
            existing_image_id = _int_or_none(image.get("id")) or int(target_state.image_id)
        except HTTPException as exc:
            if exc.status_code not in {404, 408}:
                raise

    if existing_image_id is not None:
        stamp = _now()
        template.current_image_id = existing_image_id
        template.owner_token_id = target_token.token_id
        template.owner_account_uuid = target_token.do_uuid
        template.status = TEMPLATE_STATUS_AVAILABLE
        template.last_error = None
        template.updated_at = stamp

        await _upsert_account_state(
            db,
            user_id,
            template.template_id,
            target_token,
            ACCOUNT_STATUS_AVAILABLE,
            existing_image_id,
            None,
            last_synced_at=stamp,
        )
        if source_token.token_id != target_token.token_id:
            await _upsert_account_state(
                db,
                user_id,
                template.template_id,
                source_token,
                ACCOUNT_STATUS_PENDING,
                None,
                None,
                last_synced_at=stamp,
            )

        await db.commit()
        await db.refresh(template)
        return template, target_token

    if source_token.token_id == target_token.token_id:
        message = "Template image is not available on the owner account"
        stamp = _now()
        template.status = TEMPLATE_STATUS_ERROR
        template.last_error = message
        template.updated_at = stamp
        await _upsert_account_state(
            db,
            user_id,
            template.template_id,
            target_token,
            ACCOUNT_STATUS_ERROR,
            target_state.image_id if target_state else None,
            message,
            last_synced_at=stamp,
        )
        await db.commit()
        raise HTTPException(status_code=409, detail=message)

    transfer_body: dict[str, str] = {}
    if target_token.do_uuid:
        transfer_body["recipient_uuid"] = target_token.do_uuid
    elif target_token.do_email:
        transfer_body["recipient_email"] = target_token.do_email
    else:
        raise HTTPException(status_code=400, detail="Target token missing account identity")

    template.status = TEMPLATE_STATUS_TRANSFERRING
    template.last_error = None
    template.updated_at = _now()
    await _upsert_account_state(
        db,
        user_id,
        template.template_id,
        target_token,
        ACCOUNT_STATUS_TRANSFERRING,
        template.current_image_id,
        None,
    )
    await db.commit()

    try:
        start_transfer = await do_service.do_request(
            "POST",
            f"/images/{template.current_image_id}/account_transfer",
            source_token_value,
            json_body=transfer_body,
        )

        transfer_id = _extract_transfer_id(start_transfer)
        transfer_image_id = _extract_transfer_image_id(start_transfer, template.current_image_id)

        if transfer_id:
            accept_body: dict[str, int | str] = {"transfer_id": transfer_id}
            if target_token.do_uuid:
                accept_body["recipient_uuid"] = target_token.do_uuid
            await do_service.do_request(
                "POST",
                f"/images/{template.current_image_id}/account_transfer/accept",
                target_token_value,
                json_body=accept_body,
            )

        image = await _wait_image_available(target_token_value, transfer_image_id)
        final_image_id = _int_or_none(image.get("id")) or transfer_image_id
        stamp = _now()

        template.current_image_id = final_image_id
        template.owner_token_id = target_token.token_id
        template.owner_account_uuid = target_token.do_uuid
        template.status = TEMPLATE_STATUS_AVAILABLE
        template.last_error = None
        template.updated_at = stamp

        await _upsert_account_state(
            db,
            user_id,
            template.template_id,
            target_token,
            ACCOUNT_STATUS_AVAILABLE,
            final_image_id,
            None,
            last_synced_at=stamp,
        )
        await _upsert_account_state(
            db,
            user_id,
            template.template_id,
            source_token,
            ACCOUNT_STATUS_PENDING,
            None,
            None,
            last_synced_at=stamp,
        )

        await db.commit()
        await db.refresh(template)
        return template, target_token
    except HTTPException as exc:
        message = str(exc.detail)
        stamp = _now()
        template.status = TEMPLATE_STATUS_ERROR
        template.last_error = message
        template.updated_at = stamp
        await _upsert_account_state(
            db,
            user_id,
            template.template_id,
            target_token,
            ACCOUNT_STATUS_ERROR,
            target_state.image_id if target_state else None,
            message,
            last_synced_at=stamp,
        )
        await db.commit()
        raise


async def sync_template_to_token(db: AsyncSession, user_id: str, template_id: str, target_token_id: str) -> dict:
    template = await _template_row(db, user_id, template_id)
    synced_template, _ = await _ensure_template_on_token(db, user_id, template, target_token_id)
    return await _public_for_template(db, user_id, synced_template)


async def deploy_from_template(
    db: AsyncSession,
    user_id: str,
    template_id: str,
    target_token_id: str,
    name: str,
    region: str,
    size: str,
    ssh_keys: list[str] | None,
) -> dict:
    template = await _template_row(db, user_id, template_id)
    synced_template, target_token = await _ensure_template_on_token(db, user_id, template, target_token_id)
    target_token_value = _token_value(target_token)

    body: dict[str, object] = {
        "name": name,
        "region": region,
        "size": size,
        "image": str(synced_template.current_image_id),
        "backups": False,
        "ipv6": False,
        "monitoring": True,
        "tags": ["droplet-manager", f"template:{synced_template.template_id}"],
    }
    if ssh_keys:
        body["ssh_keys"] = ssh_keys

    payload = await do_service.do_request("POST", "/droplets", target_token_value, json_body=body)
    droplet = payload.get("droplet", {})

    stamp = _now()
    synced_template.last_used_at = stamp
    synced_template.updated_at = stamp
    synced_template.status = TEMPLATE_STATUS_AVAILABLE
    synced_template.last_error = None

    await _upsert_account_state(
        db,
        user_id,
        synced_template.template_id,
        target_token,
        ACCOUNT_STATUS_AVAILABLE,
        synced_template.current_image_id,
        None,
        last_synced_at=stamp,
    )

    await db.commit()

    return {
        "template": await _public_for_template(db, user_id, synced_template),
        "droplet": droplet,
    }
