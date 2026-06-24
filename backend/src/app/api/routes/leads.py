"""
Marketing lead capture — TASK-3.5.

POST /api/v1/leads  — open (no auth); stores {email, plan} and returns 201.
Reachable as /api/v1/leads via the Next.js proxy (proxy strips /api prefix).
"""
from __future__ import annotations

import html
import uuid
from datetime import datetime, timezone

import structlog
from aiosmtplib import SMTP
from email.message import EmailMessage
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.config import get_settings
from app.db.models import Lead
from app.schemas.lead import LeadCreate, LeadResponse

log = structlog.get_logger()

PLAN_LABELS = {
    "free": "Free",
    "pro": "Pro",
    "business": "Business",
}
LEAD_SOURCE_PAGE = "/pricing"


def _lead_notification_recipients() -> list[str]:
    settings = get_settings()
    return [recipient.strip() for recipient in settings.lead_notification_to.split(",") if recipient.strip()]


def _email_enabled() -> bool:
    settings = get_settings()
    return bool(
        settings.smtp_user
        and settings.smtp_password.get_secret_value()
        and _lead_notification_recipients()
    )


def _plan_label(plan: str) -> str:
    return PLAN_LABELS.get(plan.lower(), plan)


async def _send_lead_notification_email(email: str, plan: str) -> None:
    settings = get_settings()
    recipients = _lead_notification_recipients()
    if not _email_enabled():
        log.warning(
            "lead_email_not_configured_skipping_notification",
            email=email,
            plan=plan,
        )
        return

    captured_at = datetime.now(timezone.utc).isoformat()
    plan_label = _plan_label(plan)
    safe_email = html.escape(email)
    safe_plan = html.escape(plan_label)
    safe_source = html.escape(LEAD_SOURCE_PAGE)
    safe_captured_at = html.escape(captured_at)
    text_body = (
        "New pricing page lead captured.\n\n"
        f"Email: {email}\n"
        f"Plan: {plan_label}\n"
        f"Captured at (UTC): {captured_at}\n"
        f"Source page: {LEAD_SOURCE_PAGE}\n"
    )
    html_body = f"""
    <html>
      <body style=\"font-family: Arial, sans-serif; color: #18181b; line-height: 1.5;\">
        <div style=\"max-width: 560px; margin: 0 auto; padding: 24px; border: 1px solid #e4e4e7; border-radius: 16px;\">
          <p style=\"margin: 0 0 12px; font-size: 14px; color: #6366f1; font-weight: 700;\">New pricing lead</p>
          <h2 style=\"margin: 0 0 20px; font-size: 24px; color: #09090b;\">A visitor submitted their details</h2>
          <table style=\"width: 100%; border-collapse: collapse;\">
            <tr>
              <td style=\"padding: 10px 0; color: #71717a; font-size: 14px; width: 140px;\">Email</td>
              <td style=\"padding: 10px 0; font-size: 15px; color: #09090b;\"><a href=\"mailto:{safe_email}\" style=\"color: #4f46e5; text-decoration: none;\">{safe_email}</a></td>
            </tr>
            <tr>
              <td style=\"padding: 10px 0; color: #71717a; font-size: 14px;\">Plan</td>
              <td style=\"padding: 10px 0; font-size: 15px; color: #09090b; font-weight: 600;\">{safe_plan}</td>
            </tr>
            <tr>
              <td style=\"padding: 10px 0; color: #71717a; font-size: 14px;\">Captured at (UTC)</td>
              <td style=\"padding: 10px 0; font-size: 15px; color: #09090b;\">{safe_captured_at}</td>
            </tr>
            <tr>
              <td style=\"padding: 10px 0; color: #71717a; font-size: 14px;\">Source page</td>
              <td style=\"padding: 10px 0; font-size: 15px; color: #09090b;\">{safe_source}</td>
            </tr>
          </table>
          <p style=\"margin: 20px 0 0; font-size: 13px; color: #71717a;\">Reply to this email to contact the lead directly.</p>
        </div>
      </body>
    </html>
    """.strip()

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = email
    msg["Subject"] = f"New pricing lead: {plan_label}"
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        smtp = SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=settings.smtp_tls,
        )
        await smtp.connect()
        await smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        await smtp.send_message(msg)
        await smtp.quit(        )
        log.info("lead_notification_sent", to=recipients, plan=plan)
    except Exception as exc:
        log.error(
            "lead_notification_send_failed",
            to=recipients,
            email=email,
            plan=plan,
            error=str(exc),
        )


async def _send_lead_confirmation_email(email: str, plan: str) -> None:
    """Send a confirmation email to the visitor who submitted their details on the pricing page."""
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_lead_confirmation", to=email)
        return

    plan_label = _plan_label(plan)
    safe_plan = html.escape(plan_label)
    app_url = settings.app_url.rstrip("/")

    text_body = (
        f"Forma — Pricing inquiry received\n"
        f"================================\n\n"
        f"Hi,\n\n"
        f"We received your inquiry about the {plan_label} plan. "
        f"A member of our team will be in touch shortly with details on how to get started.\n\n"
        f"In the meantime, here's a quick overview of what you can do with Forma:\n\n"
        f"  - Translate DOCX, PDF, and PPTX files\n"
        f"  - 88+ languages including Vietnamese, English, Japanese, and Chinese\n"
        f"  - Custom glossary / terminology injection for consistent, domain-accurate translations\n"
        f"  - Side-by-side review with inline correction before export\n\n"
        f"— The Forma team\n"
    )

    html_body = f"""
    <html>
      <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#18181b;background-color:#f4f4f5;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 16px;">
          <tr>
            <td align="center">
              <table width="560" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <!-- Header -->
                <tr>
                  <td style="background-color:#1a1a2e;padding:32px 40px;text-align:center;">
                    <p style="margin:0;font-size:11px;letter-spacing:3px;color:#818cf8;text-transform:uppercase;font-weight:700;">Forma</p>
                    <h1 style="margin:12px 0 0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">You&apos;re on the list</h1>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:40px;">
                    <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      Thanks for your interest in the <strong>{safe_plan}</strong> plan.
                    </p>
                    <p style="margin:0 0 28px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      A member of our team will be in touch shortly with details on how to get started.
                    </p>
                    <!-- Feature highlight -->
                    <div style="background-color:#fafafa;border-radius:8px;padding:24px;margin-bottom:28px;">
                      <p style="margin:0 0 16px;font-size:14px;font-weight:600;color:#18181b;">While you wait, here&apos;s what Forma can do:</p>
                      <table cellpadding="0" cellspacing="0" width="100%">
                        <tr>
                          <td style="padding:8px 0;font-size:14px;color:#3f3f46;">
                            <span style="color:#6366f1;font-weight:700;">&#10003;</span>&nbsp; Translate DOCX, PDF, and PPTX with format preserved
                          </td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;font-size:14px;color:#3f3f46;">
                            <span style="color:#6366f1;font-weight:700;">&#10003;</span>&nbsp; 88+ languages including Vietnamese, English, Japanese, Chinese
                          </td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;font-size:14px;color:#3f3f46;">
                            <span style="color:#6366f1;font-weight:700;">&#10003;</span>&nbsp; Custom glossaries for consistent terminology
                          </td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;font-size:14px;color:#3f3f46;">
                            <span style="color:#6366f1;font-weight:700;">&#10003;</span>&nbsp; Side-by-side review with inline correction
                          </td>
                        </tr>
                      </table>
                    </div>
                    <!-- CTA -->
                    <table cellpadding="0" cellspacing="0" style="margin:0 auto 16px;">
                      <tr>
                        <td style="background-color:#6366f1;border-radius:8px;text-align:center;">
                          <a href="{app_url}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;">Learn more about Forma</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:14px;color:#71717a;text-align:center;">
                      We typically respond within 1 business day.
                    </p>
                  </td>
                </tr>
                <!-- Footer -->
                <tr>
                  <td style="background-color:#fafafa;padding:24px 40px;border-top:1px solid #f4f4f5;">
                    <p style="margin:0;font-size:12px;color:#a1a1aa;text-align:center;">
                      — The Forma team
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """.strip()

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = email
    msg["Subject"] = f"Forma — we received your {plan_label} plan inquiry"
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        smtp = SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=settings.smtp_tls,
        )
        await smtp.connect()
        await smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        await smtp.send_message(msg)
        await smtp.quit()
        log.info("lead_confirmation_sent", to=email, plan=plan)
    except Exception as exc:
        log.error(
            "lead_confirmation_send_failed",
            to=email,
            plan=plan,
            error=str(exc),
        )


router = APIRouter(prefix="/licenses", tags=["leads"])


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture a marketing lead from the pricing page",
)
async def create_lead(
    body: LeadCreate,
    session: AsyncSession = Depends(get_session),
) -> LeadResponse:
    """Store a marketing lead and return the created row.

    - Open endpoint — no auth required (a visitor, not a logged-in user).
    - email validated as EmailStr by Pydantic → 422 on invalid format.
    - plan is a free string; no constraint beyond non-empty.
    """
    lead = Lead(
        id=str(uuid.uuid4()),
        email=str(body.email),
        plan=body.plan,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    log.info("lead_captured", lead_id=lead.id, plan=lead.plan)
    await _send_lead_notification_email(lead.email, lead.plan)
    await _send_lead_confirmation_email(lead.email, lead.plan)

    return LeadResponse(
        id=lead.id,
        email=lead.email,
        plan=lead.plan,
        created_at=lead.created_at,
    )
