import uuid


def new_email() -> str:
    return f"token_{uuid.uuid4().hex[:8]}@example.com"


def test_do_tokens_requires_auth(client):
    response = client.get("/api/do-tokens")
    assert response.status_code == 401


def test_do_proxy_requires_token_id(client):
    email = new_email()
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    response = client.get("/api/do/droplets")
    assert response.status_code == 422


def test_wizard_requires_auth(client):
    response = client.post(
        "/api/wizard/deploy-windows",
        json={
            "token_id": "tok_missing",
            "name": "win-test",
            "region": "nyc3",
            "size": "s-1vcpu-1gb",
            "image": "ubuntu-22-04-x64",
            "windows_version": "win11pro",
            "rdp_password": "Test1234!",
            "rdp_port": 33890,
        },
    )
    assert response.status_code == 401
