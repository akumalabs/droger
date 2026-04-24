import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "fakeredis://local"
os.environ["TOKEN_ENCRYPTION_KEY"] = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
os.environ["JWT_SECRET"] = "test-secret"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["SECURE_COOKIES"] = "false"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["ADMIN_EMAIL"] = "admin@dropletmanager.app"
os.environ["ADMIN_PASSWORD"] = "AdminDroplet!42"
os.environ["RESEND_API_KEY"] = ""
os.environ["SENDER_EMAIL"] = "onboarding@resend.dev"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


def _cleanup_test_db() -> None:
    db_file = Path("test.db")
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def client():
    _cleanup_test_db()
    with TestClient(app) as test_client:
        yield test_client
    _cleanup_test_db()
