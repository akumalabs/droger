def test_update_status_requires_auth(client):
    response = client.get("/api/system/update")
    assert response.status_code == 401


def test_update_status_requires_admin(client):
    client.post("/api/auth/register", json={"email": "user_update@example.com", "password": "password123"})
    response = client.get("/api/system/update")
    assert response.status_code == 403


def test_admin_can_check_and_apply_update(client, monkeypatch):
    status_payload = {
        "branch": "main",
        "local_commit": "abc123",
        "remote_commit": "def456",
        "ahead": 0,
        "behind": 1,
        "update_available": True,
        "repo_path": "/repo",
    }
    apply_payload = {
        "ok": True,
        "updated": True,
        "message": "Update applied",
        "status": {**status_payload, "local_commit": "def456", "behind": 0, "update_available": False},
        "output": "updated",
    }

    monkeypatch.setattr("app.services.update_service.get_update_status", lambda: status_payload)
    monkeypatch.setattr("app.services.update_service.apply_update", lambda: apply_payload)

    login = client.post(
        "/api/auth/login",
        json={"email": "admin@dropletmanager.app", "password": "AdminDroplet!42"},
    )
    assert login.status_code == 200

    status_response = client.get("/api/system/update")
    assert status_response.status_code == 200
    assert status_response.json()["update_available"] is True

    apply_response = client.post("/api/system/update")
    assert apply_response.status_code == 200
    assert apply_response.json()["updated"] is True
