"""
Email notification service for translation job events.

Sends emails when:
- A translation job completes successfully (US-3.7 AC-4)
- A translation job fails

Uses asyncio.create_task() so emails are fire-and-forget — they never block
the calling code. Failed sends are logged but do not propagate.
"""
from __future__ import annotations

import asyncio
import structlog
from email.message import EmailMessage

from app.core.config import get_settings

log = structlog.get_logger()


async def _send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> None:
    """Low-level email sender via aiosmtplib. Best-effort: failures are logged."""
    from aiosmtplib import SMTP

    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_email", to=to_email, subject=subject)
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body, subtype="plain")
    msg.add_alternative(html_body, subtype="html")

    try:
        smtp = SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            use_tls=settings.smtp_tls,
        )
        await smtp.connect()
        if settings.smtp_user and settings.smtp_password.get_secret_value():
            await smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        await smtp.send_message(msg)
        await smtp.quit()
        log.info("job_notification_email_sent", to=to_email, subject=subject)
    except Exception as exc:
        log.error("smtp_job_notification_failed", to=to_email, subject=subject, error=str(exc))


def _job_url(job_id: str) -> str:
    settings = get_settings()
    return f"{settings.app_url}/jobs/{job_id}"


def _job_complete_html(
    filename: str,
    job_id: str,
    source_lang: str,
    target_lang: str,
) -> str:
    url = _job_url(job_id)
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Translation Complete</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="background: #4f46e5; padding: 24px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 20px;">Translation Complete</h1>
  </div>
  <div style="border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
    <p style="margin-top: 0;">Your document has been translated successfully.</p>
    <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
      <tr>
        <td style="padding: 8px 0; color: #6b7280; width: 120px;">File</td>
        <td style="padding: 8px 0; font-weight: bold;">{filename}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280;">Direction</td>
        <td style="padding: 8px 0;">{source_lang} → {target_lang}</td>
      </tr>
    </table>
    <a href="{url}"
       style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px;
              text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 16px;">
      Review &amp; Download
    </a>
    <p style="color: #6b7280; font-size: 12px; margin-top: 24px;">
      If the button doesn't work, copy this link into your browser:<br/>
      <a href="{url}" style="color: #4f46e5; word-break: break-all;">{url}</a>
    </p>
  </div>
</body>
</html>
"""


def _job_complete_text(
    filename: str,
    job_id: str,
    source_lang: str,
    target_lang: str,
) -> str:
    url = _job_url(job_id)
    return f"""Your document has been translated successfully.

File: {filename}
Direction: {source_lang} → {target_lang}

Review & download: {url}
"""


def _job_failed_html(filename: str, job_id: str, error_msg: str) -> str:
    url = _job_url(job_id)
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Translation Failed</title>
</head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="background: #dc2626; padding: 24px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 20px;">Translation Failed</h1>
  </div>
  <div style="border: 1px solid #fca5a5; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
    <p style="margin-top: 0;">Unfortunately, your document could not be translated.</p>
    <p style="background: #fef2f2; border: 1px solid #fca5a5; padding: 12px; border-radius: 6px; font-size: 14px;">
      <strong>Error:</strong> {error_msg}
    </p>
    <p style="background: #f3f4f6; padding: 12px; border-radius: 6px; font-size: 14px;">
      <strong>File:</strong> {filename}<br/>
      <strong>Job ID:</strong> {job_id}
    </p>
    <a href="{url}"
       style="display: inline-block; background: #dc2626; color: white; padding: 12px 24px;
              text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 16px;">
      View Details
    </a>
  </div>
</body>
</html>
"""


def _job_failed_text(filename: str, job_id: str, error_msg: str) -> str:
    url = _job_url(job_id)
    return f"""Unfortunately, your document could not be translated.

File: {filename}
Job ID: {job_id}
Error: {error_msg}

View details: {url}
"""


async def send_job_complete_email(
    to_email: str,
    job_id: str,
    filename: str,
    source_lang: str,
    target_lang: str,
) -> None:
    """Send a 'translation complete' email. Fire-and-forget."""
    subject = f"Translation complete: {filename}"
    await _send_email(
        to_email=to_email,
        subject=subject,
        html_body=_job_complete_html(filename, job_id, source_lang, target_lang),
        text_body=_job_complete_text(filename, job_id, source_lang, target_lang),
    )


async def send_job_failed_email(
    to_email: str,
    job_id: str,
    filename: str,
    error_msg: str,
) -> None:
    """Send a 'translation failed' email. Fire-and-forget."""
    subject = f"Translation failed: {filename}"
    await _send_email(
        to_email=to_email,
        subject=subject,
        html_body=_job_failed_html(filename, job_id, error_msg),
        text_body=_job_failed_text(filename, job_id, error_msg),
    )


def notify_job_email(
    to_email: str,
    job_id: str,
    filename: str,
    source_lang: str,
    target_lang: str,
    is_success: bool,
    error_msg: str = "",
) -> None:
    """
    Send a job notification email asynchronously (fire-and-forget).

    Safe to call from sync or async contexts — wraps in asyncio.get_event_loop()
    or asyncio.create_task().
    """
    if is_success:
        asyncio.create_task(
            send_job_complete_email(
                to_email=to_email,
                job_id=job_id,
                filename=filename,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        )
    else:
        asyncio.create_task(
            send_job_failed_email(
                to_email=to_email,
                job_id=job_id,
                filename=filename,
                error_msg=error_msg,
            )
        )
