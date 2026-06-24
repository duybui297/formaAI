"""
Webhook endpoint routes.

All routes are prefixed with /api/v1/auth/me/webhooks (applied at app level).

GET    /api/v1/auth/me/webhooks                    — list user's webhook endpoints
POST   /api/v1/auth/me/webhooks                    — create a webhook endpoint
GET    /api/v1/auth/me/webhooks/{webhook_id}       — get one webhook endpoint
PATCH  /api/v1/auth/me/webhooks/{webhook_id}       — update a webhook endpoint
DELETE /api/v1/auth/me/webhooks/{webhook_id}       — delete a webhook endpoint
GET    /api/v1/auth/me/webhooks/{webhook_id}/deliveries — list delivery logs (paginated)
POST   /api/v1/auth/me/webhooks/{webhook_id}/test  — send a test event
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_current_active_user
from app.db.models import JobStatus, User, WebhookDelivery, WebhookEndpoint, WebhookEventType
from app.db.session import get_session
from app.schemas.webhook import (
    CreateWebhookRequest,
    UpdateWebhookRequest,
    WebhookCreatedResponse,
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookResponse,
)
from app.services.webhook_service import (
    decrypt_secret,
    dispatch_webhook,
    encrypt_secret,
    generate_webhook_secret,
)

log = structlog.get_logger()
router = APIRouter(prefix="/auth/me/webhooks", tags=["webhooks"])


async def _get_endpoint_for_user(
    session: AsyncSession,
    webhook_id: str,
    user_id: str,
) -> WebhookEndpoint:
    """Return the webhook endpoint if owned by user, else raise 404."""
    result = await session.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.user_id == user_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return endpoint


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """List all webhook endpoints owned by the current user."""
    result = await session.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.user_id == user.id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    endpoints = result.scalars().all()
    return [
        WebhookResponse(
            id=e.id,
            name=e.name,
            url=e.url,
            events=e.events or [],
            is_active=e.is_active,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in endpoints
    ]


@router.post("", response_model=WebhookCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    req: CreateWebhookRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """
    Create a new webhook endpoint.

    Returns endpoint metadata plus the plaintext secret — shown only once.
    """
    raw_secret = generate_webhook_secret()
    enc_key = request.app.state.settings.webhook_encryption_key.get_secret_value()
    encrypted_secret = encrypt_secret(raw_secret, enc_key)

    endpoint = WebhookEndpoint(
        user_id=user.id,
        name=req.name,
        url=req.url,
        encrypted_secret=encrypted_secret,
        events=req.events,
        is_active=True,
    )
    session.add(endpoint)
    await session.commit()
    await session.refresh(endpoint)

    log.info("webhook_created", endpoint_id=endpoint.id, user_id=user.id, events=req.events)

    return WebhookCreatedResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        events=endpoint.events or [],
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
        secret=raw_secret,
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """Get a single webhook endpoint by ID."""
    endpoint = await _get_endpoint_for_user(session, webhook_id, user.id)
    return WebhookResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        events=endpoint.events or [],
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    req: UpdateWebhookRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """Update a webhook endpoint (name, URL, events, active state)."""
    endpoint = await _get_endpoint_for_user(session, webhook_id, user.id)

    if req.name is not None:
        endpoint.name = req.name
    if req.url is not None:
        endpoint.url = req.url
    if req.events is not None:
        endpoint.events = req.events
    if req.is_active is not None:
        endpoint.is_active = req.is_active

    await session.commit()
    await session.refresh(endpoint)

    log.info("webhook_updated", endpoint_id=endpoint.id, user_id=user.id)

    return WebhookResponse(
        id=endpoint.id,
        name=endpoint.name,
        url=endpoint.url,
        events=endpoint.events or [],
        is_active=endpoint.is_active,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """Delete a webhook endpoint and all its delivery logs."""
    endpoint = await _get_endpoint_for_user(session, webhook_id, user.id)
    await session.delete(endpoint)
    await session.commit()
    log.info("webhook_deleted", endpoint_id=webhook_id, user_id=user.id)


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def list_deliveries(
    webhook_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """
    List delivery logs for a webhook endpoint, newest first (paginated).

    Use page and page_size to paginate. Each delivery shows request/response
    details so users can debug failed deliveries.
    """
    endpoint = await _get_endpoint_for_user(session, webhook_id, user.id)

    count_result = await session.execute(
        select(func.count(WebhookDelivery.id)).where(
            WebhookDelivery.endpoint_id == endpoint.id
        )
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    deliveries_result = await session.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == endpoint.id)
        .order_by(WebhookDelivery.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    deliveries = deliveries_result.scalars().all()

    return WebhookDeliveryListResponse(
        deliveries=[
            WebhookDeliveryResponse(
                id=d.id,
                job_id=d.job_id,
                event_type=d.event_type.value,
                attempt=d.attempt,
                status=d.status.value,
                request_method=d.request_method,
                request_url=d.request_url,
                request_headers=d.request_headers,
                response_status_code=d.response_status_code,
                response_body=d.response_body,
                error_message=d.error_message,
                duration_ms=d.duration_ms,
                created_at=d.created_at,
            )
            for d in deliveries
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    webhook_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """
    Send a test webhook event to the endpoint.

    Dispatches in the background and returns 202 Accepted immediately.
    The test delivery is logged in the delivery history with job_id=0.
    """
    endpoint = await _get_endpoint_for_user(session, webhook_id, user.id)
    enc_key = request.app.state.settings.webhook_encryption_key.get_secret_value()
    raw_secret = decrypt_secret(endpoint.encrypted_secret, enc_key)

    event_type = WebhookEventType.translation_completed

    job_data = {
        "job_id": "00000000-0000-0000-0000-000000000000",
        "status": JobStatus.done.value,
        "source_lang": "en",
        "target_lang": "vi",
        "original_filename": "test.txt",
        "output_path": None,
        "error_msg": None,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }

    asyncio.create_task(
        dispatch_webhook(
            async_sessionmaker(request.app.state.engine, expire_on_commit=False),
            endpoint.id,
            job_data["job_id"],
            job_data,
            event_type,
            raw_secret,
            enc_key,
        ),
        name=f"webhook-test-{endpoint.id[:8]}",
    )

    log.info("webhook_test_dispatched", endpoint_id=endpoint.id, user_id=user.id)
    return {"message": "Test event dispatched"}
