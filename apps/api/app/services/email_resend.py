"""Thin Resend HTTP client.

A missing or empty `RESEND_API_KEY` short-circuits to a logged warning
instead of an exception so that local dev / tests don't need a real
key — the caller treats `False` as "not delivered" and decides whether
to surface that to the user.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.logging import get_logger

log = get_logger("app.email")

RESEND_FROM = "noreply@davidfdzmorilla.dev"
RESEND_ENDPOINT = "https://api.resend.com/emails"


def _api_key() -> str | None:
    raw = os.getenv("RESEND_API_KEY")
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


async def send_email(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    api_key = _api_key()
    if api_key is None:
        log.warning("resend_api_key_missing", to=to, subject=subject[:50])
        return False

    payload: dict[str, Any] = {
        "from": RESEND_FROM,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html is not None:
        payload["html"] = html

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                RESEND_ENDPOINT,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.HTTPError as exc:
        log.error("resend_http_error", error=str(exc), to=to)
        return False

    if response.status_code >= 400:
        log.error(
            "resend_send_failed",
            status=response.status_code,
            body=response.text[:200],
            to=to,
        )
        return False

    try:
        data = response.json()
        email_id = data.get("id") if isinstance(data, dict) else None
    except ValueError:
        email_id = None

    log.info(
        "email_sent",
        to=to,
        email_id=email_id,
        subject=subject[:50],
    )
    return True


async def send_password_reset_email(
    *, to: str, token: str, base_url: str,
) -> bool:
    reset_url = f"{base_url}/reset-password?token={token}"
    subject = "Reset your radio.gofestivals password"
    text = (
        "Hi,\n\n"
        "Someone requested a password reset for your radio.gofestivals "
        "account.\n\n"
        "If this was you, click the link below to set a new password "
        "(link expires in 1 hour):\n"
        f"{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email.\n\n"
        "— radio.gofestivals\n"
        "For support: https://github.com/davidfdzmorilla/radio-gofestivals/issues"
    )
    html = f"""<!doctype html>
<html><body style="font-family:-apple-system,sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#222;">
  <h2 style="margin:0 0 16px;">Reset your password</h2>
  <p>Someone requested a password reset for your radio.gofestivals account.</p>
  <p>If this was you, click the link below (expires in 1 hour):</p>
  <p style="margin:24px 0;">
    <a href="{reset_url}"
       style="display:inline-block;padding:10px 20px;background:#d4145a;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;">
      Reset password
    </a>
  </p>
  <p style="color:#666;font-size:14px;">Or copy this link: <code>{reset_url}</code></p>
  <hr style="border:0;border-top:1px solid #eee;margin:24px 0;">
  <p style="color:#999;font-size:13px;">
    If you didn't request this, ignore this email.<br>
    For support: <a href="https://github.com/davidfdzmorilla/radio-gofestivals/issues">GitHub issues</a>
  </p>
</body></html>"""
    return await send_email(to=to, subject=subject, text=text, html=html)
