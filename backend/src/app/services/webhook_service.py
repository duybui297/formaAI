"""
Webhook delivery service (US-9.4).

Handles:
- HMAC-SHA256 payload signing
- Async HTTP POST dispatch with timeout
- Exponential backoff retry (5 attempts)
- Delivery log persistence
- Fernet encryption of webhook secrets at rest

Design: fire-and-forget from the worker's perspective.
Triggered via asyncio.create_task() so it never blocks job completion.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime

import httpx
import structlog
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    Job,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEventType,
)

log = structlog.get_logger()

_MAX_RETRIES = 5
_TIMEOUT_SECONDS = 10
_BACKOFF_BASE_MINUTES = 1.0  # delays: 1, 2, 4, 8, 16 minutes


# ---------------------------------------------------------------------------
# Secret encryption (Fernet AES-128-CBC + HMAC-SHA256)
# ---------------------------------------------------------------------------


def generate_webhook_secret() -> str:
    """Generate a cryptographically random webhook secret."""
    return secrets.token_urlsafe(32)


def encrypt_secret(raw_secret: str, key: str) -> str:
    """AES-encrypt a raw secret string. Returns base64-encoded ciphertext."""
    f = Fernet(key.encode("utf-8"))
    return f.encrypt(raw_secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str, key: str) -> str:
    """Decrypt an AES-encrypted secret. Returns plaintext."""
    f = Fernet(key.encode("utf-8"))
    return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")


# ---------------------------------------------------------------------------
# Payload signing
# ---------------------------------------------------------------------------


def sign_payload(payload: str, secret: str) -> str:
    """
    Compute HMAC-SHA256 signature of the raw JSON payload.

    Returns "sha256={hex_sig}" (GitHub-compatible format).
    """
    mac = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    )
    return f"sha256={mac.hexdigest()}"


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------


def build_webhook_payload(
    job: Job,
    event_type: WebhookEventType,
) -> dict:
    """Build the JSON payload for a webhook delivery."""
    return {
        "event": event_type.value,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {
            "job_id": job.id,
            "status": job.status.value,
            "source_lang": job.source_lang,
            "target_lang": job.target_lang,
            "original_filename": job.original_filename,
            "output_path": job.output_path,
            "error_msg": job.error_msg,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        },
    }


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


async def _send_request(
    http_client: httpx.AsyncClient,
    url: str,
    payload_json: str,
    sig: str,
    event_name: str,
) -> tuple[int | None, str | None, int | None, str | None]:
    """
    Execute a single HTTP POST attempt.

    Returns (status_code, response_body, duration_ms, error_message).
    """
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "FormaAI-Webhook/1.0",
        "X-Webhook-Event": event_name,
        "X-Webhook-Signature-256": sig,
    }

    start = time.monotonic()
    try:
        response = await http_client.post(
            url,
            content=payload_json,
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        body = response.text[:4096]
        return response.status_code, body, duration_ms, None
    except httpx.TimeoutException:
        duration_ms = int((time.monotonic() - start) * 1000)
        return None, None, duration_ms, "Request timed out"
    except httpx.ConnectError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return None, None, duration_ms, f"Connection error: {exc}"
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return None, None, duration_ms, f"Unexpected error: {exc}"


async def dispatch_webhook(
    session_factory: async_sessionmaker,
    endpoint_id: str,
    job_id: str,
    job_data: dict,
    event_type: WebhookEventType,
    raw_secret: str,
    encryption_key: str,
) -> None:
    """
    Deliver a webhook for the given endpoint + job, with exponential-backoff retry.

    Uses session_factory so it can open its own session (worker sessions may close
    before retries complete).

    job_data is a dict with keys: id, status.value, source_lang, target_lang,
    original_filename, output_path, error_msg, created_at.isoformat, updated_at.isoformat
    """
    async with session_factory() as session:
        endpoint_result = await session.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id)
        )
        endpoint = endpoint_result.scalar_one_or_none()
        if endpoint is None or not endpoint.is_active:
            log.debug("webhook_skip_inactive_endpoint", endpoint_id=endpoint_id)
            return

        payload = {
            "event": event_type.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": job_data,
        }
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        sig = sign_payload(payload_json, raw_secret)

        async with httpx.AsyncClient() as http_client:
            for attempt in range(1, _MAX_RETRIES + 1):
                status_code, response_body, duration_ms, error_msg = await _send_request(
                    http_client,
                    endpoint.url,
                    payload_json,
                    sig,
                    event_type.value,
                )

                delivery = WebhookDelivery(
                    endpoint_id=endpoint_id,
                    job_id=job_id,
                    event_type=event_type,
                    attempt=attempt,
                    status=WebhookDeliveryStatus.pending,
                    request_method="POST",
                    request_url=endpoint.url,
                    request_headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature-256": "sha256=***",
                        "X-Webhook-Event": event_type.value,
                    },
                    request_body=payload_json,
                    response_status_code=status_code,
                    response_body=response_body,
                    error_message=error_msg,
                    duration_ms=duration_ms,
                )

                if status_code is not None and 200 <= status_code < 300:
                    delivery.status = WebhookDeliveryStatus.success
                    session.add(delivery)
                    await session.commit()
                    log.info(
                        "webhook_delivered",
                        endpoint_id=endpoint_id,
                        job_id=job_id,
                        attempt=attempt,
                        status=status_code,
                    )
                    return
                else:
                    delivery.status = WebhookDeliveryStatus.failed
                    session.add(delivery)
                    await session.commit()
                    log.warning(
                        "webhook_delivery_retry",
                        endpoint_id=endpoint_id,
                        job_id=job_id,
                        attempt=attempt,
                        status=status_code,
                        error=error_msg or response_body,
                    )

                if attempt < _MAX_RETRIES:
                    delay_seconds = _BACKOFF_BASE_MINUTES * 60 * (2 ** (attempt - 1))
                    log.debug(
                        "webhook_retry_scheduled",
                        endpoint_id=endpoint_id,
                        job_id=job_id,
                        next_attempt=attempt + 1,
                        delay_seconds=delay_seconds,
                    )
                    await asyncio.sleep(delay_seconds)

    log.error(
        "webhook_all_retries_exhausted",
        endpoint_id=endpoint_id,
        job_id=job_id,
        event_type=event_type.value,
        total_attempts=_MAX_RETRIES,
    )


async def notify_webhooks_for_job(
    session_factory: async_sessionmaker,
    job: Job,
    event_type: WebhookEventType,
    encryption_key: str,
) -> None:
    """
    Query all active webhook endpoints for the job owner that subscribe to
    event_type, then fire each one in a non-blocking background task.

    Passes a serializable job_data dict so the background task doesn't need
    a live DB session.
    """
    if job.user_id is None:
        return

    job_data = {
        "job_id": job.id,
        "status": job.status.value,
        "source_lang": job.source_lang,
        "target_lang": job.target_lang,
        "original_filename": job.original_filename,
        "output_path": job.output_path,
        "error_msg": job.error_msg,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }

    async with session_factory() as session:
        result = await session.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.user_id == job.user_id,
                WebhookEndpoint.is_active == True,
            )
        )
        endpoints = list(result.scalars().all())

    if not endpoints:
        return

    for endpoint in endpoints:
        if event_type.value in (endpoint.events or []):
            raw_secret = decrypt_secret(endpoint.encrypted_secret, encryption_key)
            asyncio.create_task(
                dispatch_webhook(
                    session_factory,
                    endpoint.id,
                    job.id,
                    job_data,
                    event_type,
                    raw_secret,
                    encryption_key,
                ),
                name=f"webhook-{endpoint.id[:8]}",
            )
