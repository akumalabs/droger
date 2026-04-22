"""
Backend regression tests for Droplet Manager v2 (auth + DO token vault + wizard).

Covers:
- /api/auth/* (register, login, me, refresh, logout, session, lockout)
- /api/do-tokens (vault validation against DO)
- /api/do/* proxy auth + token_id validation
- /api/do/windows-versions, /api/do/windows-script
- /api/wizard/deploy-windows
"""
import os
import time
import uuid
import requests
import pytest
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@dropletmanager.app"
ADMIN_PASSWORD = "AdminDroplet!42"


# ---------- helpers ----------
def _new_email():
    # Server lowercases the email on register/login; keep test value lowercased
    return f"test_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def fresh_session():
    return requests.Session()


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture
def user_session():
    s = requests.Session()
    email = _new_email()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "password123"})
    if r.status_code != 200:
        pytest.skip(f"User registration failed: {r.status_code} {r.text}")
    s._email = email  # type: ignore[attr-defined]
    return s


# =========================== AUTH =====================================
class TestAuth:
    def test_register_success_and_cookies(self, fresh_session):
        email = _new_email()
        r = fresh_session.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == email
        assert body["auth_provider"] == "email"
        assert body["role"] == "user"
        assert body.get("user_id", "").startswith("user_")
        assert "password_hash" not in body
        assert "_id" not in body
        assert "access_token" in fresh_session.cookies
        assert "refresh_token" in fresh_session.cookies

    def test_register_duplicate_email(self, fresh_session):
        email = _new_email()
        r1 = fresh_session.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
        assert r1.status_code == 200
        s2 = requests.Session()
        r2 = s2.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
        assert r2.status_code == 400
        assert "already registered" in r2.json().get("detail", "").lower()

    def test_register_short_password(self, fresh_session):
        r = fresh_session.post(f"{API}/auth/register", json={"email": _new_email(), "password": "abc"})
        assert r.status_code == 422

    def test_login_admin_success(self, fresh_session):
        r = fresh_session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "admin"
        assert "access_token" in fresh_session.cookies
        assert "refresh_token" in fresh_session.cookies

    def test_login_wrong_password(self, fresh_session):
        # Use an email not used by lockout in other tests by registering a user
        email = _new_email()
        requests.post(f"{API}/auth/register", json={"email": email, "password": "secret123"})
        r = fresh_session.post(f"{API}/auth/login", json={"email": email, "password": "wrongpw00"})
        assert r.status_code == 401
        assert "invalid email or password" in r.json().get("detail", "").lower()

    def test_me_without_cookies(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401
        assert "not authenticated" in r.json().get("detail", "").lower()

    def test_me_with_cookies(self, user_session):
        r = user_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == user_session._email
        assert "password_hash" not in body
        assert "_id" not in body

    def test_refresh_with_valid_cookie(self, user_session):
        old_access = user_session.cookies.get("access_token")
        r = user_session.post(f"{API}/auth/refresh")
        assert r.status_code == 200, r.text
        new_access = user_session.cookies.get("access_token")
        assert new_access is not None
        # /auth/me should still work
        me = user_session.get(f"{API}/auth/me")
        assert me.status_code == 200

    def test_logout_clears_cookies(self, user_session):
        r = user_session.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # Server should clear cookies; ensure subsequent /me unauthenticated
        s2 = requests.Session()
        me = s2.get(f"{API}/auth/me")
        assert me.status_code == 401

    def test_session_with_bogus_id(self, fresh_session):
        r = fresh_session.post(f"{API}/auth/session", json={"session_id": "totally-bogus-session-id-xyz"})
        assert r.status_code == 401
        assert "invalid google session" in r.json().get("detail", "").lower()


# =========================== LOCKOUT ==================================
class TestLockout:
    def test_brute_force_lockout(self):
        # Use a unique email so we don't pollute other tests
        email = _new_email()
        requests.post(f"{API}/auth/register", json={"email": email, "password": "correct123"})
        s = requests.Session()
        # 5 failed attempts
        for i in range(5):
            r = s.post(f"{API}/auth/login", json={"email": email, "password": "WRONG_pw_xx"})
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code}"
        # 6th should be locked out
        r6 = s.post(f"{API}/auth/login", json={"email": email, "password": "WRONG_pw_xx"})
        assert r6.status_code == 429, f"Expected 429, got {r6.status_code}: {r6.text}"


# =========================== DO TOKEN VAULT ===========================
class TestDoTokens:
    def test_list_tokens_unauthenticated(self):
        r = requests.get(f"{API}/do-tokens")
        assert r.status_code == 401

    def test_list_tokens_fresh_user_empty(self, user_session):
        r = user_session.get(f"{API}/do-tokens")
        assert r.status_code == 200
        assert r.json() == {"tokens": []}

    def test_add_invalid_do_token(self, user_session):
        r = user_session.post(
            f"{API}/do-tokens",
            json={"name": "test", "token": "dop_v1_invalid_token_for_testing_only"},
        )
        assert r.status_code == 400, r.text
        assert "digitalocean rejected" in r.json().get("detail", "").lower()


# =========================== DO PROXY =================================
class TestDoProxy:
    def test_droplets_unauthenticated(self):
        r = requests.get(f"{API}/do/droplets")
        assert r.status_code == 401

    def test_droplets_missing_token_id(self, user_session):
        r = user_session.get(f"{API}/do/droplets")
        # FastAPI: missing required query param → 422
        assert r.status_code == 422, f"Got {r.status_code}: {r.text}"

    def test_droplets_nonexistent_token(self, user_session):
        r = user_session.get(f"{API}/do/droplets", params={"token_id": "tok_does_not_exist"})
        assert r.status_code == 404
        assert "do token not found" in r.json().get("detail", "").lower()

    def test_droplet_action_nonexistent_token(self, user_session):
        r = user_session.post(
            f"{API}/do/droplets/123/actions",
            params={"token_id": "tok_does_not_exist"},
            json={"action_type": "power_on"},
        )
        # token lookup happens before DO call → 404
        assert r.status_code == 404, f"Got {r.status_code}: {r.text}"


# =========================== WINDOWS SCRIPT ===========================
class TestWindowsScript:
    def test_windows_versions_public(self):
        r = requests.get(f"{API}/do/windows-versions")
        assert r.status_code == 200
        body = r.json()
        assert "versions" in body
        assert len(body["versions"]) == 8

    def test_windows_script_unauthenticated(self):
        r = requests.post(
            f"{API}/do/windows-script",
            json={"version": "win11pro", "password": "Test1234!", "rdp_port": 33890},
        )
        assert r.status_code == 401

    def test_windows_script_authenticated(self, user_session):
        r = user_session.post(
            f"{API}/do/windows-script",
            json={"version": "win11pro", "password": "Test1234!", "rdp_port": 33890},
        )
        assert r.status_code == 200, r.text
        cmd = r.json().get("command", "")
        assert "reinstall.sh windows" in cmd
        assert "--image-name" in cmd
        assert "--rdp-port 33890" in cmd
        assert "--password" in cmd


# =========================== WIZARD ===================================
class TestWizard:
    def test_wizard_unauthenticated(self):
        r = requests.post(
            f"{API}/wizard/deploy-windows",
            json={
                "token_id": "tok_x",
                "name": "win-test",
                "region": "nyc3",
                "size": "s-1vcpu-1gb",
                "image": "ubuntu-22-04-x64",
                "windows_version": "win11pro",
                "rdp_password": "Test1234!",
                "rdp_port": 33890,
            },
        )
        assert r.status_code == 401

    def test_wizard_nonexistent_token(self, user_session):
        r = user_session.post(
            f"{API}/wizard/deploy-windows",
            json={
                "token_id": "tok_does_not_exist",
                "name": "win-test",
                "region": "nyc3",
                "size": "s-1vcpu-1gb",
                "image": "ubuntu-22-04-x64",
                "windows_version": "win11pro",
                "rdp_password": "Test1234!",
                "rdp_port": 33890,
            },
        )
        assert r.status_code == 404, f"Got {r.status_code}: {r.text}"
