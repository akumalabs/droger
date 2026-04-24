import uuid
from fastapi import HTTPException


def new_email() -> str:
    return f"tpl_{uuid.uuid4().hex[:8]}@example.com"


def test_templates_requires_auth(client):
    response = client.get("/api/templates")
    assert response.status_code == 401


def test_template_snapshot_sync_deploy_flow(client, monkeypatch):
    email = new_email()
    register = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert register.status_code == 200

    accounts = {
        "raw-token-a": {
            "uuid": "acc-a",
            "email": "a@example.com",
            "images": {123: "available"},
        },
        "raw-token-b": {
            "uuid": "acc-b",
            "email": "b@example.com",
            "images": {},
        },
    }
    calls: list[tuple[str, str, str]] = []

    async def fake_validate_do_token(raw_token: str):
        account = accounts.get(raw_token)
        if not account:
            raise HTTPException(status_code=400, detail="bad token")
        return {
            "uuid": account["uuid"],
            "email": account["email"],
            "droplet_limit": 25,
        }

    async def fake_do_request(method: str, path: str, token: str, params=None, json_body=None):
        calls.append((method, path, token))
        account = accounts.get(token)
        if not account:
            raise HTTPException(status_code=401, detail="unknown token")

        if method == "POST" and path.endswith("/account_transfer/accept"):
            return {"ok": True}

        if method == "POST" and path.endswith("/account_transfer"):
            image_id = int(path.split("/")[2])
            if image_id not in account["images"]:
                raise HTTPException(status_code=404, detail="image not found")
            recipient_uuid = (json_body or {}).get("recipient_uuid")
            target = next((item for item in accounts.values() if item["uuid"] == recipient_uuid), None)
            if not target:
                raise HTTPException(status_code=400, detail="recipient not found")
            account["images"].pop(image_id, None)
            target["images"][image_id] = "available"
            return {"transfer_id": 321}

        if method == "GET" and path.startswith("/images/"):
            image_id = int(path.split("/")[2])
            status = account["images"].get(image_id)
            if status is None:
                raise HTTPException(status_code=404, detail="missing")
            return {
                "image": {
                    "id": image_id,
                    "status": status,
                    "type": "snapshot",
                    "name": "base-snapshot",
                }
            }

        if method == "POST" and path == "/droplets":
            payload = json_body or {}
            return {
                "droplet": {
                    "id": 987654,
                    "name": payload.get("name"),
                    "image": {"id": payload.get("image")},
                    "region": {"slug": payload.get("region")},
                    "size_slug": payload.get("size"),
                    "status": "new",
                }
            }

        raise HTTPException(status_code=500, detail=f"Unhandled call {method} {path}")

    monkeypatch.setattr("app.services.token_service.validate_do_token", fake_validate_do_token)
    monkeypatch.setattr("app.services.do_service.do_request", fake_do_request)

    token_a = client.post("/api/do-tokens", json={"name": "Account A", "token": "raw-token-a"})
    assert token_a.status_code == 200
    token_a_id = token_a.json()["id"]

    token_b = client.post("/api/do-tokens", json={"name": "Account B", "token": "raw-token-b"})
    assert token_b.status_code == 200
    token_b_id = token_b.json()["id"]

    create = client.post(
        "/api/templates/from-snapshot",
        json={
            "token_id": token_a_id,
            "snapshot_id": 123,
            "label": "Win Base",
            "notes": "April patch set",
            "source_droplet_id": 456,
            "snapshot_name": "base-snapshot",
        },
    )
    assert create.status_code == 200
    created = create.json()

    assert created["label"] == "Win Base"
    assert created["notes"] == "April patch set"
    assert created["owner_token_id"] == token_a_id
    assert created["owner_account_uuid"] == "acc-a"
    assert created["status"] == "available"

    created_availability = {row["token_id"]: row for row in created["availability"]}
    assert created_availability[token_a_id]["status"] == "available"
    assert created_availability[token_b_id]["status"] == "pending"

    sync = client.post(f"/api/templates/{created['id']}/sync", json={"token_id": token_b_id})
    assert sync.status_code == 200
    synced = sync.json()
    assert synced["owner_token_id"] == token_b_id
    assert synced["status"] == "available"

    synced_availability = {row["token_id"]: row for row in synced["availability"]}
    assert synced_availability[token_b_id]["status"] == "available"
    assert synced_availability[token_b_id]["image_id"] == 123
    assert synced_availability[token_a_id]["status"] == "pending"

    deploy = client.post(
        f"/api/templates/{created['id']}/deploy",
        json={
            "token_id": token_b_id,
            "name": "from-template-01",
            "region": "nyc3",
            "size": "s-1vcpu-1gb",
            "ssh_keys": ["12345"],
        },
    )
    assert deploy.status_code == 200
    deployed = deploy.json()
    assert deployed["template"]["owner_token_id"] == token_b_id
    assert deployed["template"]["status"] == "available"
    assert deployed["droplet"]["name"] == "from-template-01"

    list_resp = client.get("/api/templates")
    assert list_resp.status_code == 200
    templates = list_resp.json()["templates"]
    assert len(templates) == 1
    listed = templates[0]
    listed_availability = {row["token_id"]: row for row in listed["availability"]}
    assert listed_availability[token_b_id]["status"] == "available"
    assert listed_availability[token_a_id]["status"] == "pending"

    transfer_calls = [c for c in calls if c[0] == "POST" and c[1].endswith("/account_transfer")]
    assert len(transfer_calls) == 1
