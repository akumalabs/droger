"""
Backend tests for Droplet Manager v2 — P2 features:
- Email verification (register issues token, /verify-email, /resend-verification)
- Password reset (/forgot-password, /reset-password)
- TTL indexes on login_attempts / email_verification_tokens / password_reset_tokens

Mongo is read directly to fetch tokens (avoids needing an inbox) and to
inspect indexes. Real Resend API is configured but tests use mailinator-style
addresses to avoid spamming real inboxes; the API call result is not asserted.
"""
import os
import uuid
import requests
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ---------- helpers ----------
def _new_email() -> str:
    # mailinator domain — never delivers a real email
    return f"test_{uuid.uuid4().hex[:10]}@mailinator.com"


def _register(email: str, password: str = "password123") -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


# ============================================================
# Email verification
# ============================================================
class TestEmailVerification:
    def test_register_creates_unverified_user_and_token(self, mongo):
        email = _new_email()
        s = _register(email)
        body = s.get(f"{API}/auth/me").json()
        assert body["email"] == email
        assert body["email_verified"] is False, "Newly registered user must be unverified"

        # Token row exists in db
        doc = mongo.email_verification_tokens.find_one({"email": email})
        assert doc is not None, "verification token row missing"
        assert isinstance(doc.get("token"), str) and len(doc["token"]) >= 20
        assert doc.get("user_id", "").startswith("user_")
        exp = doc.get("expires_at")
        assert isinstance(exp, datetime), f"expires_at must be datetime, got {type(exp)}"

    def test_verify_email_with_valid_token_marks_user_verified(self, mongo):
        email = _new_email()
        _register(email)
        doc = mongo.email_verification_tokens.find_one({"email": email})
        token = doc["token"]
        user_id = doc["user_id"]

        r = requests.post(f"{API}/auth/verify-email", json={"token": token})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # token row deleted
        gone = mongo.email_verification_tokens.find_one({"token": token})
        assert gone is None, "verification token must be deleted after use"
        # user marked verified
        u = mongo.users.find_one({"user_id": user_id})
        assert u.get("email_verified") is True

    def test_verify_email_with_bogus_token_returns_400(self):
        r = requests.post(f"{API}/auth/verify-email", json={"token": "bogus-not-real-xyz"})
        assert r.status_code == 400
        assert "invalid or expired" in r.json().get("detail", "").lower()

    def test_resend_verification_unauthed_401(self):
        r = requests.post(f"{API}/auth/resend-verification")
        assert r.status_code == 401

    def test_resend_verification_unverified_user(self, mongo):
        email = _new_email()
        s = _register(email)
        # capture original token
        orig = mongo.email_verification_tokens.find_one({"email": email})
        assert orig is not None
        orig_token = orig["token"]

        r = s.post(f"{API}/auth/resend-verification")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "sent" in body and isinstance(body["sent"], bool)

        # original deleted, exactly one new token exists for that user
        rows = list(mongo.email_verification_tokens.find({"email": email}))
        assert len(rows) == 1, f"expected 1 token after resend, got {len(rows)}"
        assert rows[0]["token"] != orig_token, "resend must create a NEW token, not reuse old one"

    def test_resend_verification_for_verified_user_returns_already_verified(self, mongo):
        email = _new_email()
        s = _register(email)
        doc = mongo.email_verification_tokens.find_one({"email": email})
        # verify first
        requests.post(f"{API}/auth/verify-email", json={"token": doc["token"]})
        # now resend
        r = s.post(f"{API}/auth/resend-verification")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("already_verified") is True


# ============================================================
# Password reset
# ============================================================
class TestPasswordReset:
    def test_forgot_password_unknown_email_returns_ok(self, mongo):
        # No row created, but response is 200 ok (no enumeration)
        unknown = _new_email()
        r = requests.post(f"{API}/auth/forgot-password", json={"email": unknown})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}
        row = mongo.password_reset_tokens.find_one({"user_id": {"$exists": True}, "_id": {"$exists": True}})  # placeholder query
        # specifically check no token tied to this email's user (user doesn't exist)
        u = mongo.users.find_one({"email": unknown})
        assert u is None

    def test_forgot_password_known_email_creates_token(self, mongo):
        email = _new_email()
        _register(email, "originalPW1")
        r = requests.post(f"{API}/auth/forgot-password", json={"email": email})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        u = mongo.users.find_one({"email": email})
        rows = list(mongo.password_reset_tokens.find({"user_id": u["user_id"]}))
        assert len(rows) == 1, f"expected 1 reset token row, got {len(rows)}"
        row = rows[0]
        assert isinstance(row.get("expires_at"), datetime)
        assert row.get("used") is False

    def test_reset_password_with_valid_token_changes_password(self, mongo):
        email = _new_email()
        _register(email, "originalPW1")
        requests.post(f"{API}/auth/forgot-password", json={"email": email})
        u = mongo.users.find_one({"email": email})
        row = mongo.password_reset_tokens.find_one({"user_id": u["user_id"]})
        token = row["token"]

        r = requests.post(
            f"{API}/auth/reset-password", json={"token": token, "password": "newPassXYZ9"}
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # token marked used
        used = mongo.password_reset_tokens.find_one({"token": token})
        assert used.get("used") is True

        # old password fails
        r_old = requests.post(
            f"{API}/auth/login", json={"email": email, "password": "originalPW1"}
        )
        assert r_old.status_code == 401, "Old password must no longer work"

        # new password works
        r_new = requests.post(
            f"{API}/auth/login", json={"email": email, "password": "newPassXYZ9"}
        )
        assert r_new.status_code == 200, r_new.text

    def test_reset_password_reuse_returns_400(self, mongo):
        email = _new_email()
        _register(email, "originalPW1")
        requests.post(f"{API}/auth/forgot-password", json={"email": email})
        u = mongo.users.find_one({"email": email})
        token = mongo.password_reset_tokens.find_one({"user_id": u["user_id"]})["token"]
        # first use OK
        r1 = requests.post(
            f"{API}/auth/reset-password", json={"token": token, "password": "anotherPW1"}
        )
        assert r1.status_code == 200
        # second use rejected
        r2 = requests.post(
            f"{API}/auth/reset-password", json={"token": token, "password": "yetanotherPW2"}
        )
        assert r2.status_code == 400
        assert "invalid" in r2.json().get("detail", "").lower() or "used" in r2.json().get("detail", "").lower()

    def test_reset_password_invalid_token_returns_400(self):
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": "totally-bogus-reset-token", "password": "whateverPW1"},
        )
        assert r.status_code == 400

    def test_reset_password_expired_token_returns_400(self, mongo):
        # craft an expired row directly
        email = _new_email()
        _register(email, "originalPW1")
        u = mongo.users.find_one({"email": email})
        expired_token = f"expired_{uuid.uuid4().hex}"
        mongo.password_reset_tokens.insert_one(
            {
                "token": expired_token,
                "user_id": u["user_id"],
                "expires_at": datetime.now(timezone.utc) - timedelta(hours=2),
                "used": False,
                "created_at": datetime.now(timezone.utc),
            }
        )
        r = requests.post(
            f"{API}/auth/reset-password",
            json={"token": expired_token, "password": "whateverPW1"},
        )
        assert r.status_code == 400
        assert "expired" in r.json().get("detail", "").lower()


# ============================================================
# TTL indexes
# ============================================================
class TestTTLIndexes:
    def test_login_attempts_ttl_index(self, mongo):
        idxs = mongo.login_attempts.index_information()
        ttl = [v for k, v in idxs.items() if v.get("expireAfterSeconds") is not None]
        assert ttl, f"No TTL index on login_attempts. Indexes: {idxs}"
        assert any(
            v.get("key", [(None,)])[0][0] == "last_attempt"
            and v.get("expireAfterSeconds") == 900
            for v in ttl
        ), f"Expected TTL on last_attempt with expireAfterSeconds=900: {ttl}"

    def test_email_verification_tokens_ttl_index(self, mongo):
        idxs = mongo.email_verification_tokens.index_information()
        ttl = [v for k, v in idxs.items() if v.get("expireAfterSeconds") is not None]
        assert ttl, f"No TTL index on email_verification_tokens. Indexes: {idxs}"
        assert any(
            v.get("key", [(None,)])[0][0] == "expires_at"
            and v.get("expireAfterSeconds") == 0
            for v in ttl
        ), f"Expected TTL on expires_at expireAfterSeconds=0: {ttl}"

    def test_password_reset_tokens_ttl_index(self, mongo):
        idxs = mongo.password_reset_tokens.index_information()
        ttl = [v for k, v in idxs.items() if v.get("expireAfterSeconds") is not None]
        assert ttl, f"No TTL index on password_reset_tokens. Indexes: {idxs}"
        assert any(
            v.get("key", [(None,)])[0][0] == "expires_at"
            and v.get("expireAfterSeconds") == 0
            for v in ttl
        ), f"Expected TTL on expires_at expireAfterSeconds=0: {ttl}"


# ============================================================
# Lockout regression (email-only identifier + native datetime)
# ============================================================
class TestLockoutRegression:
    def test_brute_force_lockout_after_5_with_native_datetime(self, mongo):
        email = _new_email()
        _register(email, "correctPW1")
        s = requests.Session()
        for i in range(5):
            r = s.post(f"{API}/auth/login", json={"email": email, "password": "WRONG_pw_xx"})
            assert r.status_code == 401, f"attempt {i+1}: {r.status_code} {r.text}"
        r6 = s.post(f"{API}/auth/login", json={"email": email, "password": "WRONG_pw_xx"})
        assert r6.status_code == 429, f"Expected 429 on 6th attempt, got {r6.status_code}"

        # verify the row stores native datetime (not string) so TTL can reap it
        row = mongo.login_attempts.find_one({"identifier": f"email:{email}"})
        assert row is not None, "login_attempts row missing"
        assert isinstance(row.get("last_attempt"), datetime), (
            f"last_attempt must be native datetime for TTL, got {type(row.get('last_attempt'))}"
        )
