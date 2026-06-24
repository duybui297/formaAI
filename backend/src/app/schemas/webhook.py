"""
Pydantic schemas for webhook endpoints (US-9.4).
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.db.models import WebhookDeliveryStatus


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

AVAILABLE_EVENTS = [
    ("translation.completed", "Triggered when a translation job completes successfully"),
    ("translation.failed", "Triggered when a translation job fails"),
]


# ---------------------------------------------------------------------------
# Webhook endpoint schemas
# ---------------------------------------------------------------------------


class CreateWebhookRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=10, max_length=2048)
    events: list[str] = Field(
        ...,
        min_length=1,
        description="List of event types to subscribe to. "
        f"Available: {[e[0] for e in AVAILABLE_EVENTS]}",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        import urllib.parse

        parsed = urllib.parse.urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Webhook URL must use http or https")
        if not parsed.netloc:
            raise ValueError("Webhook URL is missing a host")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        allowed = {e[0] for e in AVAILABLE_EVENTS}
        invalid = [e for e in v if e not in allowed]
        if invalid:
            raise ValueError(f"Invalid event types: {invalid}. Allowed: {sorted(allowed)}")
        return v


class UpdateWebhookRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    url: str | None = Field(default=None, min_length=10, max_length=2048)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import urllib.parse

        parsed = urllib.parse.urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Webhook URL must use http or https")
        if not parsed.netloc:
            raise ValueError("Webhook URL is missing a host")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        allowed = {e[0] for e in AVAILABLE_EVENTS}
        invalid = [e for e in v if e not in allowed]
        if invalid:
            raise ValueError(f"Invalid event types: {invalid}. Allowed: {sorted(allowed)}")
        return v


class WebhookResponse(BaseModel):
    id: str
    name: str
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebhookCreatedResponse(BaseModel):
    id: str
    name: str
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    secret: str


# ---------------------------------------------------------------------------
# Webhook delivery log schemas
# ---------------------------------------------------------------------------


class WebhookDeliveryResponse(BaseModel):
    id: str
    job_id: str
    event_type: str
    attempt: int
    status: WebhookDeliveryStatus
    request_method: str
    request_url: str
    request_headers: dict | None
    response_status_code: int | None
    response_body: str | None
    error_message: str | None
    duration_ms: int | None
    created_at: datetime


class WebhookDeliveryListResponse(BaseModel):
    deliveries: list[WebhookDeliveryResponse]
    total: int
    page: int
    page_size: int
