import uuid


def new_email() -> str:
    return f"test_{uuid.uuid4().hex[:10]}@example.com"


def test_register_login_me_refresh_logout(client):
    email = new_email()

    register = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert register.status_code == 200
    body = register.json()
    assert body["email"] == email
    assert body["auth_provider"] == "email"
    assert body["email_verified"] is False

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email

    refresh = client.post("/api/auth/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["ok"] is True

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    me_after = client.get("/api/auth/me")
    assert me_after.status_code == 401


def test_login_invalid_password(client):
    email = new_email()
    client.post("/api/auth/register", json={"email": email, "password": "password123"})
    bad = client.post("/api/auth/login", json={"email": email, "password": "bad-password"})
    assert bad.status_code == 401


def test_verify_email_and_resend(client):
    email = new_email()
    register = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert register.status_code == 200

    resend = client.post("/api/auth/resend-verification")
    assert resend.status_code == 200
    assert resend.json().get("ok") is True

    bad_verify = client.post("/api/auth/verify-email", json={"token": "bogus-token"})
    assert bad_verify.status_code == 400


def test_forgot_and_reset_password(client):
    email = new_email()
    client.post("/api/auth/register", json={"email": email, "password": "password123"})

    forgot = client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    assert forgot.json() == {"ok": True}

    bad_reset = client.post("/api/auth/reset-password", json={"token": "bogus", "password": "newpass123"})
    assert bad_reset.status_code == 400
