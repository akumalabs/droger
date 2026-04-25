import asyncio
import logging
import resend
from app.core.config import get_settings

logger = logging.getLogger("mailer")


async def send_email(to: str, subject: str, html: str) -> bool:
    settings = get_settings()
    api_key = (settings.resend_api_key or "").strip()
    sender = (settings.sender_email or "").strip() or "onboarding@resend.dev"
    if not api_key:
        logger.warning("email_fallback to=%s subject=%s", to, subject)
        return False

    resend.api_key = api_key
    params = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    try:
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info("email_sent to=%s subject=%s", to, subject)
        return True
    except Exception:
        logger.exception("email_send_failed to=%s", to)
        return False


def _wrap(body: str) -> str:
    return (
        "<!DOCTYPE html><html><body style='background:#050505;color:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0;padding:0;'>"
        "<table width='100%' cellpadding='0' cellspacing='0' style='background:#050505;padding:40px 0;'><tr><td align='center'>"
        "<table width='560' cellpadding='0' cellspacing='0' style='background:#0a0a0b;border:1px solid #222;padding:32px;'><tr><td>"
        "<div style='font-weight:900;font-size:22px;letter-spacing:-0.02em;color:#fff;margin-bottom:24px;'><span style='display:inline-block;background:#fff;color:#000;padding:2px 6px;margin-right:8px;'>DM</span> Droplet Manager</div>"
        f"{body}"
        "<p style='font-family:monospace;font-size:11px;color:#666;margin-top:40px;border-top:1px solid #222;padding-top:16px;'>"
        "If that wasn't you, ignore this email.</p>"
        "</td></tr></table></td></tr></table></body></html>"
    )


async def send_verification_email(to: str, link: str) -> bool:
    body = (
        "<h2 style='font-weight:700;color:#fff;font-size:20px;margin:0 0 16px;'>Verify your email</h2>"
        "<p style='color:#a3a3a3;font-size:14px;line-height:1.6;'>Click below to verify your email. This link expires in 24 hours.</p>"
        f"<p style='margin:28px 0;'><a href='{link}' style='display:inline-block;background:#00E5FF;color:#000;text-decoration:none;padding:12px 20px;font-weight:600;'>Verify email</a></p>"
        f"<p style='color:#666;font-size:12px;'>Or paste this URL: <span style='color:#00E5FF;word-break:break-all;'>{link}</span></p>"
    )
    return await send_email(to, "Verify your Droplet Manager email", _wrap(body))


async def send_password_reset_email(to: str, link: str) -> bool:
    body = (
        "<h2 style='font-weight:700;color:#fff;font-size:20px;margin:0 0 16px;'>Reset your password</h2>"
        "<p style='color:#a3a3a3;font-size:14px;line-height:1.6;'>Click below to set a new password. This link expires in 1 hour.</p>"
        f"<p style='margin:28px 0;'><a href='{link}' style='display:inline-block;background:#00E5FF;color:#000;text-decoration:none;padding:12px 20px;font-weight:600;'>Reset password</a></p>"
        f"<p style='color:#666;font-size:12px;'>Or paste this URL: <span style='color:#00E5FF;word-break:break-all;'>{link}</span></p>"
    )
    return await send_email(to, "Reset your Droplet Manager password", _wrap(body))
