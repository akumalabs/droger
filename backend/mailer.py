"""Resend email wrapper. Falls back to console-log when no API key configured."""
import os
import asyncio
import logging
from typing import Optional

import resend

logger = logging.getLogger("mailer")


def _api_key() -> Optional[str]:
    return os.environ.get("RESEND_API_KEY") or None


def _sender() -> str:
    return os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True if actually sent, False on log-fallback."""
    api_key = _api_key()
    if not api_key:
        logger.warning(f"[mailer] RESEND_API_KEY missing. Would send to {to}: {subject}\n{html}")
        return False
    resend.api_key = api_key
    params = {
        "from": _sender(),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"[mailer] Sent email to {to} (id={result.get('id') if isinstance(result, dict) else '?'})")
        return True
    except Exception as e:
        logger.error(f"[mailer] Failed to send to {to}: {e}")
        return False


# ---- Templated emails ------------------------------------------------- #
APP_NAME = "Droplet Manager"


def _wrap(body: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="background:#050505;color:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0;padding:0;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#050505;padding:40px 0;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#0a0a0b;border:1px solid #222;padding:32px;">
      <tr><td>
        <div style="font-family:'Chivo',sans-serif;font-weight:900;font-size:22px;letter-spacing:-0.02em;color:#fff;margin-bottom:24px;">
          <span style="display:inline-block;background:#fff;color:#000;padding:2px 6px;margin-right:8px;">DM</span> {APP_NAME}
        </div>
        {body}
        <p style="font-family:monospace;font-size:11px;color:#666;margin-top:40px;border-top:1px solid #222;padding-top:16px;">
          You received this because someone requested it on {APP_NAME}.
          If that wasn't you, ignore this email.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""


async def send_verification_email(to: str, link: str) -> bool:
    body = f"""
<h2 style="font-family:'Chivo',sans-serif;font-weight:700;color:#fff;font-size:20px;margin:0 0 16px;">Verify your email</h2>
<p style="color:#a3a3a3;font-size:14px;line-height:1.6;">Click the button below to confirm your email address. This link expires in 24 hours.</p>
<p style="margin:28px 0;"><a href="{link}" style="display:inline-block;background:#00E5FF;color:#000;text-decoration:none;padding:12px 20px;font-weight:600;font-family:sans-serif;">Verify email</a></p>
<p style="color:#666;font-size:12px;">Or paste this URL: <span style="color:#00E5FF;word-break:break-all;">{link}</span></p>
"""
    return await send_email(to, f"Verify your {APP_NAME} email", _wrap(body))


async def send_password_reset_email(to: str, link: str) -> bool:
    body = f"""
<h2 style="font-family:'Chivo',sans-serif;font-weight:700;color:#fff;font-size:20px;margin:0 0 16px;">Reset your password</h2>
<p style="color:#a3a3a3;font-size:14px;line-height:1.6;">Click below to set a new password. This link expires in 1 hour.</p>
<p style="margin:28px 0;"><a href="{link}" style="display:inline-block;background:#00E5FF;color:#000;text-decoration:none;padding:12px 20px;font-weight:600;font-family:sans-serif;">Reset password</a></p>
<p style="color:#666;font-size:12px;">Or paste this URL: <span style="color:#00E5FF;word-break:break-all;">{link}</span></p>
"""
    return await send_email(to, f"Reset your {APP_NAME} password", _wrap(body))
