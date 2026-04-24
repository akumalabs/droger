from app.services.windows import build_windows_user_data


def test_windows_versions_public(client):
    response = client.get("/api/do/windows-versions")
    assert response.status_code == 200
    data = response.json()
    keys = [v["key"] for v in data["versions"]]
    assert "win11pro" in keys
    assert "win10ltsc" in keys


def test_windows_user_data_builder():
    user_data = build_windows_user_data("win11pro", "Test1234!", 33890)
    assert "droger-autowin.log" in user_data
    assert "python3 -m http.server 80" in user_data
    assert "droger-progress" in user_data
    assert "base64 -d" in user_data
    assert "bash /root/.droger_autowin_cmd.sh" in user_data


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
    assert response.status_code == 403
    assert "disabled" in response.json().get("detail", "").lower()
