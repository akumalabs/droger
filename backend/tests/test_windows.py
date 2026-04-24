def test_windows_versions_public(client):
    response = client.get("/api/do/windows-versions")
    assert response.status_code == 200
    data = response.json()
    keys = [v["key"] for v in data["versions"]]
    assert "win11pro" in keys
    assert "win10ltsc" in keys


def test_windows_script_requires_auth(client):
    response = client.post(
        "/api/do/windows-script",
        json={"version": "win11pro", "password": "Test1234!", "rdp_port": 33890},
    )
    assert response.status_code == 401


import uuid


def test_windows_script_authenticated(client):
    email = f"win_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    response = client.post(
        "/api/do/windows-script",
        json={"version": "win11pro", "password": "Test1234!", "rdp_port": 33890},
    )
    assert response.status_code == 200
    command = response.json()["command"]
    assert "reinstall.sh windows" in command
    assert "--rdp-port 33890" in command
