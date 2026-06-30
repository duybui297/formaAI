"""
Auth routes: signup, login, logout, refresh, forgot-password, reset-password, verify-email.

POST   /v1/auth/signup            — create account + default Free license + send verify email
POST   /v1/auth/verify-email      — validate verify token, set user.email_verified=True
POST   /v1/auth/login             — email+password → 15-min access token + 30-d httpOnly refresh cookie
POST   /v1/auth/refresh           — rotate refresh cookie, issue new 15-min access token (CSRF required)
POST   /v1/auth/logout            — clear cookie, revoke refresh
GET    /v1/auth/me                — return current user info (protected)
PATCH  /v1/auth/me                — update full_name
PATCH  /v1/auth/me/password       — change password
POST   /v1/auth/me/avatar         — upload avatar image
GET    /v1/auth/me/notifications  — get notification preferences
PATCH  /v1/auth/me/notifications  — update notification preferences
GET    /v1/auth/me/translation-defaults   — get translation defaults
PATCH  /v1/auth/me/translation-defaults   — update translation defaults
GET    /v1/auth/me/api-keys       — list API keys
POST   /v1/auth/me/api-keys       — create API key
DELETE /v1/auth/me/api-keys/{key_id}      — revoke API key
GET    /v1/auth/me/workspace      — get workspace members + pending invites
POST   /v1/auth/me/workspace/invite       — invite member
DELETE /v1/auth/me/workspace/invite/{invite_id}  — revoke invite
DELETE /v1/auth/me/workspace/member/{member_id}   — remove member
POST   /v1/auth/forgot-password   — send reset email (or silent success for security)
POST   /v1/auth/reset-password    — validate token + update password
"""
from __future__ import annotations

import asyncio
import html
import hashlib
import os
import secrets
import secrets as _secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import structlog
from aiosmtplib import SMTP
from email.message import EmailMessage
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_password_reset_token,
    hash_password,
    verify_password,
)
from app.db.models import ApiKey, EmailVerificationToken, License, LicenseStatus, LicenseTier, PasswordResetToken, TeamInvite, User
from app.licensing.keygen import generate_license_key, hash_key
from app.db.session import get_session
from app.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    AvatarResponse,
    ChangePasswordRequest,
    CreateApiKeyRequest,
    ForgotPasswordRequest,
    InviteMemberRequest,
    InviteResponse,
    LoginRequest,
    MessageResponse,
    MemberResponse,
    NotificationPreferencesResponse,
    RefreshTokenResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    TranslationDefaultsResponse,
    UpdateMeRequest,
    UpdateNotificationPreferencesRequest,
    UpdateTranslationDefaultsRequest,
    UserResponse,
    VerifyEmailRequest,
    WorkspaceResponse,
)
from app.api.deps import get_current_active_user, get_redis

log = structlog.get_logger()
router = APIRouter(prefix="/v1/auth", tags=["auth"])

CSRF_COOKIE = "csrf_token"
REFRESH_COOKIE = "refresh_token"
ACCESS_COOKIE = "forma_access_token"

# Helpers
async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


def _lockout_key(user_id: str, ip: str) -> str:
    return f"lockout:{user_id}:{ip}"


def _attempt_key(user_id: str, ip: str) -> str:
    return f"login_attempts:{user_id}:{ip}"


async def _check_lockout(
    redis: Redis, user_id: str, ip: str, settings
) -> None:
    key = _lockout_key(user_id, ip)
    locked = await redis.get(key)
    if locked:
        ttl = await redis.ttl(key)
        wait_sec = max(int(ttl), 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many failed attempts. Please try again in {wait_sec // 60 + 1} minute(s)."
            ),
        )


async def _record_failed_attempt(
    redis: Redis, user_id: str, ip: str, settings
) -> None:
    key = _attempt_key(user_id, ip)
    lockout_key = _lockout_key(user_id, ip)

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, settings.login_attempt_window_minutes * 60)
    results = await pipe.execute()
    count = results[0]  # current count after incr

    if count >= settings.login_max_attempts:
        await redis.setex(
            lockout_key,
            settings.login_lockout_minutes * 60,
            "1",
        )
        # Also expire the attempt counter so window resets after lockout
        await redis.delete(key)
        log.warning("user_locked_out", user_id=user_id, ip=ip)


async def _clear_failed_attempts(redis: Redis, user_id: str, ip: str) -> None:
    await redis.delete(_attempt_key(user_id, ip))
    await redis.delete(_lockout_key(user_id, ip))


def _csrf_token(request: Request) -> str:
    return request.cookies.get(CSRF_COOKIE, "")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _send_reset_email(
    to_email: str, token: str, base_url: str
) -> None:
    """Send a password-reset email with a clean HTML template.

    Falls back to plain-text if SMTP is not configured.
    """
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_email", to=to_email)
        return

    reset_url = f"{base_url}/reset-password?token={token}"
    safe_url = html.escape(reset_url)

    text_body = (
        "Forma — Password Reset\n"
        "==================\n\n"
        "We received a request to reset your password.\n\n"
        f"Click the link below to set a new password (this link expires in 1 hour):\n"
        f"{reset_url}\n\n"
        "If you didn't request a password reset, you can safely ignore this email — "
        "your password has not been changed.\n"
        f"\n— The Forma team\n"
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
                    <h1 style="margin:12px 0 0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">Password Reset</h1>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:40px;">
                    <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      We received a request to reset your password for your Forma account.
                    </p>
                    <p style="margin:0 0 28px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      Click the button below to set a new password. This link will expire in <strong>1 hour</strong>.
                    </p>
                    <!-- CTA Button -->
                    <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
                      <tr>
                        <td style="background-color:#6366f1;border-radius:8px;text-align:center;">
                          <a href="{safe_url}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;">Reset Password</a>
                        </td>
                      </tr>
                    </table>
                    <!-- Fallback link -->
                    <p style="margin:0 0 24px;font-size:14px;line-height:1.5;color:#71717a;text-align:center;">
                      If the button doesn't work, copy and paste this link into your browser:<br>
                      <a href="{safe_url}" style="color:#6366f1;word-break:break-all;text-decoration:none;">{safe_url}</a>
                    </p>
                    <!-- Security note -->
                    <div style="background-color:#fafafa;border-left:3px solid #e4e4e7;padding:16px 20px;border-radius:0 8px 8px 0;margin-bottom:24px;">
                      <p style="margin:0;font-size:14px;color:#71717a;line-height:1.5;">
                        <strong style="color:#3f3f46;">Security notice:</strong> If you didn't request a password reset, please ignore this email. Your password has not been changed — no action is needed.
                      </p>
                    </div>
                    <!-- AI Translation context -->
                    <p style="margin:0;font-size:14px;line-height:1.5;color:#71717a;">
                      Forma uses AI to translate DOCX, PDF, and PPTX documents with format fidelity — so your translated files are ready to use, not just readable.
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
    msg["To"] = to_email
    msg["Subject"] = "Reset your Forma password"
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
        log.info("reset_email_sent", to=to_email)
    except Exception as exc:
        log.error("smtp_send_failed", to=to_email, error=str(exc))


async def _send_welcome_email(to_email: str, full_name: str) -> None:
    """Send a welcome email after account registration with a clean HTML template."""
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_welcome_email", to=to_email)
        return

    first_name = full_name.split()[0] if full_name else None
    greeting = f"Hi {html.escape(first_name)}" if first_name else "Welcome"
    safe_name = html.escape(full_name) if full_name else ""
    app_url = settings.app_url.rstrip("/")

    text_body = (
        f"Forma — Welcome!\n"
        f"==================\n\n"
        f"{greeting},\n\n"
        f"Your Forma account is ready. Here's what you can do next:\n\n"
        f"  1. Upload a document (DOCX, PDF, PPTX)\n"
        f"  2. Choose your source and target language\n"
        f"  3. Translate with Qwen — format stays intact\n"
        f"  4. Review in the side-by-side editor and export\n\n"
        f"Get started: {app_url}\n\n"
        f"Key features:\n"
        f"  - Translate DOCX, PDF, and PPTX files\n"
        f"  - Supports Vietnamese, English, Japanese, Chinese, and 88 more languages\n"
        f"  - Custom glossary / terminology injection for consistent translations\n"
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
                    <h1 style="margin:12px 0 0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">Welcome aboard</h1>
                  </td>
                </tr>
                <!-- Body -->
                <tr>
                  <td style="padding:40px;">
                    <p style="margin:0 0 12px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      {greeting}{',' if first_name else ''} your account is ready.
                    </p>
                    <p style="margin:0 0 32px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      Here's what you can do with Forma:
                    </p>
                    <!-- Feature list -->
                    <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:32px;">
                      <tr>
                        <td style="padding:16px;background-color:#fafafa;border-radius:8px;border:1px solid #f4f4f5;vertical-align:top;width:50%;">
                          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#18181b;">Translate DOCX, PDF, PPTX</p>
                          <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">Upload your documents — the original format is preserved in the translated output.</p>
                        </td>
                        <td width="16"></td>
                        <td style="padding:16px;background-color:#fafafa;border-radius:8px;border:1px solid #f4f4f5;vertical-align:top;width:50%;">
                          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#18181b;">88+ languages</p>
                          <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">Vietnamese, English, Japanese, Chinese, and many more language pairs supported.</p>
                        </td>
                      </tr>
                      <tr height="12"></tr>
                      <tr>
                        <td style="padding:16px;background-color:#fafafa;border-radius:8px;border:1px solid #f4f4f5;vertical-align:top;width:50%;">
                          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#18181b;">Custom glossaries</p>
                          <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">Inject terminology to ensure consistent, domain-accurate translations.</p>
                        </td>
                        <td width="16"></td>
                        <td style="padding:16px;background-color:#fafafa;border-radius:8px;border:1px solid #f4f4f5;vertical-align:top;width:50%;">
                          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#18181b;">Side-by-side review</p>
                          <p style="margin:0;font-size:13px;color:#71717a;line-height:1.5;">Edit translations inline before exporting — no layout rework needed.</p>
                        </td>
                      </tr>
                    </table>
                    <!-- CTA Button -->
                    <table cellpadding="0" cellspacing="0" style="margin:0 auto 20px;">
                      <tr>
                        <td style="background-color:#6366f1;border-radius:8px;text-align:center;">
                          <a href="{app_url}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;">Start translating</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0;font-size:14px;color:#71717a;text-align:center;">
                      Already have a license key? <a href="{app_url}/activate" style="color:#6366f1;text-decoration:none;">Activate it here</a>
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
    msg["To"] = to_email
    msg["Subject"] = "Welcome to Forma — start translating"
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
        log.info("welcome_email_sent", to=to_email)
    except Exception as exc:
        log.error("smtp_welcome_send_failed", to=to_email, error=str(exc))


async def _send_workspace_invite_email(
    to_email: str,
    inviter_name: str,
    workspace_name: str,
    invite_token: str,
    invite_url: str,
    expires_days: int,
) -> None:
    """Send a workspace invitation email with an accept-link."""
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_invite_email", to=to_email)
        return

    safe_url = html.escape(invite_url)
    days_str = f"{expires_days} days" if expires_days != 1 else "1 day"

    text_body = (
        f"Forma — Workspace Invitation\n"
        f"=========================\n\n"
        f"{inviter_name} invited you to join their workspace \"{workspace_name}\" on Forma.\n"
        f"Click the link below to accept the invitation (expires in {days_str}):\n"
        f"{invite_url}\n\n"
        f"If you don't have a Forma account, you'll be prompted to create one.\n"
        f"\n— The Forma team\n"
    )

    html_body = f"""
    <html>
      <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#18181b;background-color:#f4f4f5;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 16px;">
          <tr>
            <td align="center">
              <table width="560" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <tr>
                  <td style="background-color:#1a1a2e;padding:32px 40px;text-align:center;">
                    <p style="margin:0;font-size:11px;letter-spacing:3px;color:#818cf8;text-transform:uppercase;font-weight:700;">Forma</p>
                    <h1 style="margin:12px 0 0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">You're invited!</h1>
                  </td>
                </tr>
                <tr>
                  <td style="padding:40px;">
                    <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      <strong>{inviter_name}</strong> has invited you to join the workspace <strong>"{workspace_name}"</strong> on Forma.
                    </p>
                    <p style="margin:0 0 28px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      Click the button below to accept your invitation. This invite expires in <strong>{days_str}</strong>.
                    </p>
                    <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
                      <tr>
                        <td style="background-color:#6366f1;border-radius:8px;text-align:center;">
                          <a href="{safe_url}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;">Accept Invitation</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0 0 24px;font-size:14px;line-height:1.5;color:#71717a;text-align:center;">
                      If the button doesn't work, copy and paste this link into your browser:<br>
                      <a href="{safe_url}" style="color:#6366f1;word-break:break-all;">{invite_url}</a>
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:24px 0 0;font-size:12px;color:#a1a1aa;text-align:center;">
                If you didn't expect this invitation, you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = f"Join {inviter_name}'s Forma workspace"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
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
        log.info("smtp_invite_sent", to=to_email)
    except Exception as exc:
        log.error("smtp_invite_send_failed", to=to_email, error=str(exc))


async def _send_verification_email(
    to_email: str, token: str, base_url: str
) -> None:
    """US-1.1: send the email-verification link (TTL 24h)."""
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        log.warning("smtp_not_configured_skipping_verification_email", to=to_email)
        return

    verify_url = f"{base_url}/verify-email?token={token}"
    safe_url = html.escape(verify_url)

    text_body = (
        "Welcome to Forma!\n"
        "==================\n\n"
        "Thanks for signing up. Please verify your email address by clicking "
        "the link below. This link expires in 24 hours.\n\n"
        f"{verify_url}\n\n"
        "If you didn't create this account, you can safely ignore this email.\n"
        "\n— The Forma team\n"
    )

    html_body = f"""
    <html>
      <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#18181b;background-color:#f4f4f5;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:40px 16px;">
          <tr>
            <td align="center">
              <table width="560" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
                <tr>
                  <td style="background-color:#1a1a2e;padding:32px 40px;text-align:center;">
                    <p style="margin:0;font-size:11px;letter-spacing:3px;color:#818cf8;text-transform:uppercase;font-weight:700;">Forma</p>
                    <h1 style="margin:12px 0 0;font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">Verify your email</h1>
                  </td>
                </tr>
                <tr>
                  <td style="padding:40px;">
                    <p style="margin:0 0 20px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      Thanks for signing up for Forma. Click the button below to verify your email and activate your account.
                    </p>
                    <p style="margin:0 0 28px;font-size:16px;line-height:1.6;color:#3f3f46;">
                      This link will expire in <strong>24 hours</strong>.
                    </p>
                    <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
                      <tr>
                        <td style="background-color:#6366f1;border-radius:8px;text-align:center;">
                          <a href="{safe_url}" style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;letter-spacing:-0.2px;">Verify Email</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:0 0 24px;font-size:14px;line-height:1.5;color:#71717a;text-align:center;">
                      If the button doesn't work, copy and paste this link into your browser:<br>
                      <a href="{safe_url}" style="color:#6366f1;word-break:break-all;text-decoration:none;">{safe_url}</a>
                    </p>
                    <div style="background-color:#fafafa;border-left:3px solid #e4e4e7;padding:16px 20px;border-radius:0 8px 8px 0;">
                      <p style="margin:0;font-size:14px;color:#71717a;line-height:1.5;">
                        <strong style="color:#3f3f46;">Didn't sign up?</strong> You can safely ignore this email — no account will be created.
                      </p>
                    </div>
                  </td>
                </tr>
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
    msg["To"] = to_email
    msg["Subject"] = "Verify your Forma email"
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
        log.info("verification_email_sent", to=to_email)
    except Exception as exc:
        log.error("smtp_verification_send_failed", to=to_email, error=str(exc))


# Routes
@router.post("/signup", status_code=201)
async def signup(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    """US-1.1 Email + password signup.

    1. IP rate-limit (5/min)
    2. Reject duplicate email with 409 + "Email already registered. Sign in?"
    3. In a single transaction: create User, default Free License (TRIAL/14d),
       and EmailVerificationToken (TTL 24h)
    4. Send verification email (fire-and-forget so response is not blocked)
    5. Login is blocked until user clicks the verification link
    """
    settings = get_settings()
    ip = _client_ip(request)

    # --- IP rate-limit 5/min -------------------------------------------------
    rl_key = f"signup_rate:{ip}"
    pipe = redis.pipeline()
    pipe.incr(rl_key)
    pipe.expire(rl_key, 60)
    results = await pipe.execute()
    count = results[0]
    if count > settings.signup_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts from this IP. Please try again in a minute.",
        )

    # --- Duplicate email guard ----------------------------------------------
    existing = await _get_user_by_email(session, body.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered. Sign in?",
        )

    # --- User + License (Free=TRIAL) + EmailVerificationToken in 1 tx --------
    now = datetime.now(timezone.utc)
    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        email_verified=False,
    )
    session.add(user)
    await session.flush()  # populate user.id without committing

    raw_key = generate_license_key(
        settings.license_signing_secret.get_secret_value(),
        user.id,
    )
    free_license = License(
        key_hash=hash_key(raw_key),
        tier=LicenseTier.TRIAL,             # Free plan maps to TRIAL (plans.py)
        status=LicenseStatus.ACTIVE,
        customer_id=user.id,
        max_devices=1,
        issued_at=now,
        activated_at=now,
        expired_at=now + timedelta(days=14),
    )
    session.add(free_license)

    verify_token = secrets.token_urlsafe(48)
    evt = EmailVerificationToken(
        user_id=user.id,
        token=verify_token,
        expires_at=now + timedelta(
            minutes=settings.email_verification_token_expire_minutes
        ),
    )
    session.add(evt)

    await session.commit()
    await session.refresh(user)

    log.info(
        "user_signed_up",
        user_id=user.id,
        email=user.email,
        license_id=free_license.id,
    )

    # Fire-and-forget verification email — do not block the 201 response.
    asyncio.create_task(
        _send_verification_email(user.email, verify_token, settings.app_url)
    )

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "avatar_url": user.avatar_url,
        "message": (
            "Account created. Please check your email to verify your address "
            "before signing in. The link expires in 24 hours."
        ),
    }


@router.post("/verify-email", status_code=200)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """US-1.1: validate the email-verification token and mark user.email_verified=True.

    Used when the user clicks the link in the verification email.
    After success, the user can sign in via /v1/auth/login.
    """
    result = await session.execute(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token == body.token)
        .where(EmailVerificationToken.used_at.is_(None))
    )
    evt = result.scalar_one_or_none()

    if evt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used verification token",
        )

    # Normalise naive datetime (SQLite) to UTC-aware before comparing
    expires_at = evt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired. Please sign up again to receive a new link.",
        )

    user = await session.get(User, evt.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    user.email_verified = True
    evt.used_at = datetime.now(timezone.utc)
    await session.commit()

    log.info("email_verified", user_id=user.id)
    return MessageResponse(
        message="Email verified successfully. You can now sign in."
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    settings = get_settings()
    ip = _client_ip(request)
    user = await _get_user_by_email(session, body.email)

    password_ok = user is not None and verify_password(body.password, user.hashed_password)

    if user is not None:
        await _check_lockout(redis, user.id, ip, settings)

    if not password_ok or user is None:
        detail = "Incorrect email or password"
        if user is not None:
            await _record_failed_attempt(redis, user.id, ip, settings)
            log.info("login_failed", user_id=user.id, ip=ip, reason="bad_password")
        else:
            log.info("login_failed", email=body.email.lower(), ip=ip, reason="unknown_user")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Please verify your email before signing in. "
                "Check your inbox for the verification link (expires in 24 hours)."
            ),
        )

    await _clear_failed_attempts(redis, user.id, ip)

    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    # Set rotating refresh token cookie
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf,
        httponly=False,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )
    # Set access token as a readable cookie so AppLayout's isAuthenticated() check works
    response.set_cookie(
        key=ACCESS_COOKIE,
        value="1",  # presence of cookie = authenticated; token is in Authorization header
        httponly=False,
        samesite="lax",
        secure=False,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    log.info("user_logged_in", user_id=user.id, email=user.email, ip=ip)

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
) -> RefreshTokenResponse:
    settings = get_settings()

    raw_refresh = request.cookies.get(REFRESH_COOKIE, "")
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    payload = decode_refresh_token(raw_refresh)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    ip = _client_ip(request)
    await _check_lockout(redis, user_id, ip, settings)

    csrf_header = request.headers.get("x-csrf-token", "")
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    if not csrf_header or csrf_header != csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    # Verify user still exists and is active
    from app.db.session import get_session as _get_s
    async with _get_s() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated",
            )

    # Rotate: issue new access + refresh tokens
    new_access = create_access_token(data={"sub": user_id})
    new_refresh = create_refresh_token(data={"sub": user_id})
    new_csrf = secrets.token_urlsafe(32)

    # Set new cookies (path=/api so it doesn't conflict with static assets if any)
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=new_refresh,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=new_csrf,
        httponly=False,
        samesite="strict",
        secure=False,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/",
    )

    log.info("token_refreshed", user_id=user_id, ip=ip)

    return RefreshTokenResponse(access_token=new_access)


@router.post("/logout", status_code=204, response_model=None)
async def logout(request: Request, response: Response) -> None:
    """Clear refresh and CSRF cookies. Client drops local access token separately."""
    response.delete_cookie(key=REFRESH_COOKIE, path="/")
    response.delete_cookie(key=CSRF_COOKIE, path="/")
    response.delete_cookie(key="forma_access_token", path="/")


@router.get("/me")
async def get_me(
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        avatar_url=user.avatar_url,
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateMeRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """Update the current user's profile (full_name only; email is immutable)."""
    if body.full_name is not None:
        user.full_name = body.full_name
        await session.commit()
        await session.refresh(user)

    log.info("user_profile_updated", user_id=user.id)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        avatar_url=user.avatar_url,
    )


# 2 MB max avatar size
_MAX_AVATAR_BYTES = 2 * 1024 * 1024
_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@router.post("/me/avatar", response_model=AvatarResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> AvatarResponse:
    """Upload a new avatar image for the current user."""
    if file.size is not None and file.size > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 2 MB.",
        )

    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}. Use JPEG, PNG, GIF, or WebP.",
        )

    # Determine extension
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")
    filename = f"{user.id}{ext}"
    avatar_dir = "/data/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    avatar_path = os.path.join(avatar_dir, filename)

    # Read async file into memory, then write synchronously
    contents = await file.read()
    with open(avatar_path, "wb") as f:
        f.write(contents)

    # Use API proxy path so browser can load the avatar
    avatar_url = f"/api/auth/me/avatar/{user.id}{ext}"
    user.avatar_url = avatar_url
    await session.commit()

    return AvatarResponse(avatar_url=avatar_url)


@router.get("/me/avatar/{filename}", include_in_schema=False)
async def get_avatar(filename: str) -> Response:
    """Serve avatar image files (no auth required for performance)."""
    avatar_dir = "/data/avatars"
    avatar_path = os.path.join(avatar_dir, filename)
    if not os.path.isfile(avatar_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    with open(avatar_path, "rb") as f:
        contents = f.read()
    ext = os.path.splitext(filename)[1].lower()
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_types.get(ext, "application/octet-stream")
    return Response(content=contents, media_type=media_type)


@router.patch("/me/password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Change the current user's password. Requires the current password."""
    if not verify_password(body.current_password, user.hashed_password):
        log.info("password_change_failed_wrong_current", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.hashed_password = hash_password(body.new_password)
    await session.commit()

    log.info("password_changed", user_id=user.id)
    return MessageResponse(message="Password changed successfully.")


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
    check_only: bool = Query(False),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    user = await _get_user_by_email(session, body.email)

    if check_only and user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email.",
        )

    if user is None:
        return MessageResponse(
            message="If an account with that email exists, a reset link has been sent."
        )

    # Rate-limit: skip token creation and email send if a reset was already requested
    # within the cooldown window.
    settings = get_settings()
    rate_limit_key = f"forgot_password:{body.email.lower()}"
    if not check_only:
        cooldown_ttl = await redis.get(rate_limit_key)
        if cooldown_ttl is not None:
            return MessageResponse(
                message="If an account with that email exists, a reset link has been sent."
            )
        await redis.setex(rate_limit_key, settings.forgot_password_cooldown_seconds, "1")

    # Invalidate any existing unused reset tokens for this user
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    for old_token in result.scalars().all():
        old_token.used_at = datetime.now(timezone.utc)

    raw_token = generate_password_reset_token(user.email)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )

    prt = PasswordResetToken(
        token=raw_token,
        user_id=user.id,
        expires_at=expires_at,
    )
    session.add(prt)
    await session.commit()

    if not check_only:
        await _send_reset_email(user.email, raw_token, settings.app_url)

    return MessageResponse(
        message="If an account with that email exists, a reset link has been sent."
    )


@router.post("/reset-password", status_code=200)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    result = await session.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token == body.token)
        .where(PasswordResetToken.used_at.is_(None))
    )
    prt = result.scalar_one_or_none()

    if prt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Normalise naive datetime (SQLite) to UTC-aware before comparing
    expires_at = prt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one.",
        )

    # Look up user
    user_result = await session.execute(
        select(User).where(User.id == prt.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Update password
    user.hashed_password = hash_password(body.new_password)
    prt.used_at = datetime.now(timezone.utc)

    await session.commit()

    log.info("password_reset_complete", user_id=user.id, email=user.email)

    return MessageResponse(message="Password has been reset successfully. Please log in.")


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------

_DEFAULT_PREFS = {
    "email_job_complete": True,
    "email_job_failed": True,
    "email_license_expiry": True,
    "email_license_revoked": False,
    "email_marketing": False,
}


@router.get("/me/notifications", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    user: User = Depends(get_current_active_user),
) -> NotificationPreferencesResponse:
    prefs = user.notification_preferences or {}
    return NotificationPreferencesResponse(
        **{k: prefs.get(k, v) for k, v in _DEFAULT_PREFS.items()}
    )


@router.patch("/me/notifications", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: UpdateNotificationPreferencesRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesResponse:
    current = user.notification_preferences or {}
    patch = body.model_dump(exclude_unset=True)
    current.update(patch)
    user.notification_preferences = current
    await session.commit()
    return NotificationPreferencesResponse(
        **{k: current.get(k, v) for k, v in _DEFAULT_PREFS.items()}
    )


# ---------------------------------------------------------------------------
# Translation defaults
# ---------------------------------------------------------------------------

_DEFAULT_TRANS_DEFAULTS = {
    "preferred_source_lang": None,
    "preferred_target_lang": None,
    "default_glossary_id": None,
    "auto_detect": False,
}


@router.get("/me/translation-defaults", response_model=TranslationDefaultsResponse)
async def get_translation_defaults(
    user: User = Depends(get_current_active_user),
) -> TranslationDefaultsResponse:
    td = user.translation_defaults or {}
    return TranslationDefaultsResponse(
        **{k: td.get(k, v) for k, v in _DEFAULT_TRANS_DEFAULTS.items()}
    )


@router.patch("/me/translation-defaults", response_model=TranslationDefaultsResponse)
async def update_translation_defaults(
    body: UpdateTranslationDefaultsRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> TranslationDefaultsResponse:
    current = user.translation_defaults or {}
    patch = body.model_dump(exclude_unset=True)
    current.update(patch)
    user.translation_defaults = current
    await session.commit()
    return TranslationDefaultsResponse(
        **{k: current.get(k, v) for k, v in _DEFAULT_TRANS_DEFAULTS.items()}
    )


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

def _generate_key() -> tuple[str, str, str]:
    """Generate a raw API key, its prefix, and SHA-256 hash.

    Returns (raw_key, prefix, hash).
    """
    raw = f"ftn_{_secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    h = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, h


@router.get("/me/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyResponse]:
    keys = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .where(ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
        )
        for k in keys.scalars().all()
    ]


@router.post("/me/api-keys", status_code=201, response_model=ApiKeyCreatedResponse)
async def create_api_key(
    body: CreateApiKeyRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreatedResponse:
    raw_key, prefix, key_hash = _generate_key()
    now = datetime.now(timezone.utc)
    key = ApiKey(
        id=str(_uuid.uuid4()),
        user_id=user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        created_at=now,
    )
    session.add(key)
    await session.commit()
    return ApiKeyCreatedResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        raw_key=raw_key,
    )


@router.delete("/me/api-keys/{key_id}", status_code=204, response_model=None)
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        raise HTTPException(status_code=404, detail="API key not found")
    key.revoked_at = datetime.now(timezone.utc)
    await session.commit()


# ---------------------------------------------------------------------------
# Team Workspace
# ---------------------------------------------------------------------------


@router.get("/me/workspace", response_model=WorkspaceResponse)
async def get_workspace(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceResponse:
    # Members: owner + any user with the same workspace_id
    workspace_id = user.workspace_id or user.id
    members_result = await session.execute(
        select(User)
        .where(
            (User.id == workspace_id) | (User.workspace_id == workspace_id)
        )
        .where(User.deleted_at.is_(None))
    )
    members = [
        MemberResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role="owner" if u.id == workspace_id else "member",
            joined_at=u.created_at,
        )
        for u in members_result.scalars().all()
    ]

    # Pending invites (only workspace owner can see these)
    invites_result = await session.execute(
        select(TeamInvite)
        .where(
            TeamInvite.workspace_owner_id == workspace_id,
            TeamInvite.status == "pending",
            TeamInvite.expires_at > datetime.now(timezone.utc),
        )
        .order_by(TeamInvite.created_at.desc())
    )
    pending = [
        InviteResponse(
            id=i.id,
            email=i.email,
            role=i.role,
            status=i.status,
            created_at=i.created_at,
            expires_at=i.expires_at,
        )
        for i in invites_result.scalars().all()
    ]

    return WorkspaceResponse(members=members, pending_invites=pending)


@router.post("/me/workspace/invite", status_code=201, response_model=InviteResponse)
async def invite_member(
    body: InviteMemberRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> InviteResponse:
    workspace_id = user.workspace_id or user.id
    token = _secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    invite = TeamInvite(
        id=str(_uuid.uuid4()),
        workspace_owner_id=workspace_id,
        email=body.email.lower(),
        role=body.role,
        token=token,
        status="pending",
        created_at=datetime.now(timezone.utc),
        expires_at=expires,
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)

    # Send invite email
    settings = get_settings()
    inviter_name = user.full_name or user.email
    workspace_name = "Forma Workspace"
    invite_url = f"{settings.app_url}/invite?token={token}"
    await _send_workspace_invite_email(
        to_email=invite.email,
        inviter_name=inviter_name,
        workspace_name=workspace_name,
        invite_token=token,
        invite_url=invite_url,
        expires_days=7,
    )
    log.info("team_invite_sent", invite_id=invite.id, email=invite.email)

    return InviteResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        status=invite.status,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
    )


@router.delete("/me/workspace/invite/{invite_id}", status_code=204, response_model=None)
async def revoke_invite(
    invite_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    workspace_id = user.workspace_id or user.id
    result = await session.execute(
        select(TeamInvite)
        .where(
            TeamInvite.id == invite_id,
            TeamInvite.workspace_owner_id == workspace_id,
        )
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    await session.delete(invite)
    await session.commit()


@router.delete("/me/workspace/member/{member_id}", status_code=204, response_model=None)
async def remove_member(
    member_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    workspace_id = user.workspace_id or user.id
    if member_id == workspace_id:
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    result = await session.execute(
        select(User).where(
            User.id == member_id,
            User.workspace_id == workspace_id,
            User.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    member.workspace_id = None
    await session.commit()
