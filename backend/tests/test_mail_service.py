import asyncio

from app.core.config import get_settings
from app.services import mail_service


def test_send_email_uses_config_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "sender_email", "no-reply@example.com")

    sent = {}

    def fake_send(params):
        sent.update(params)
        return {"id": "mail_123"}

    monkeypatch.setattr("resend.Emails.send", fake_send)

    ok = asyncio.run(mail_service.send_email("user@example.com", "Hello", "<p>Hi</p>"))

    assert ok is True
    assert sent["from"] == "no-reply@example.com"
    assert sent["to"] == ["user@example.com"]


def test_send_email_without_api_key_returns_false(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "sender_email", "no-reply@example.com")

    def fail_send(_params):
        raise AssertionError("resend should not be called without API key")

    monkeypatch.setattr("resend.Emails.send", fail_send)

    ok = asyncio.run(mail_service.send_email("user@example.com", "Hello", "<p>Hi</p>"))

    assert ok is False
