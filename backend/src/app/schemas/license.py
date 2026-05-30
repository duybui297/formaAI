"""Pydantic schemas for license management endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.db.models import LicenseStatus, LicenseTier


class CreateLicenseRequest(BaseModel):
    """Body for POST /api/admin/licenses."""

    tier: LicenseTier
    customer_id: str = Field(..., description="UUID of the user who owns this license")
    max_devices: int = Field(..., gt=0, description="Maximum device activations allowed")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional fixed expiry datetime (UTC). "
        "If omitted the license has no hard expiry until explicitly set.",
    )

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        import uuid as _uuid
        try:
            _uuid.UUID(v)
        except ValueError:
            raise ValueError("customer_id must be a valid UUID")
        return v


class LicenseActivityResponse(BaseModel):
    """Single audit-log entry."""

    id: str
    license_id: str
    event_type: str
    actor_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class LicenseResponse(BaseModel):
    """Response for a single license.

    The ``raw_key`` field is populated exactly once — only on the initial
    201 Create response.  It is ``None`` on all subsequent reads because the
    raw key is never persisted (only its SHA-256 hash is stored).
    """

    id: str
    tier: LicenseTier
    status: LicenseStatus
    customer_id: str
    max_devices: int
    issued_at: datetime
    activated_at: Optional[datetime]
    expired_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    # Returned exactly once at creation; None on all reads thereafter.
    raw_key: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TASK-2.2: Activate license schemas
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TASK-3.3: Self-serve checkout schema
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    """Body for POST /api/licenses/checkout (self-serve, authenticated user)."""

    plan: str = Field(
        ...,
        description="Plan key: 'free', 'pro', or 'business'",
    )

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        from app.licensing.plans import VALID_PLANS
        if v.lower() not in VALID_PLANS:
            raise ValueError(
                f"Unknown plan '{v}'. Valid plans: {sorted(VALID_PLANS)}"
            )
        return v.lower()


class ActivateRequest(BaseModel):
    """Body for POST /api/licenses/activate."""

    raw_key: str = Field(..., description="Raw license key in XXXX-XXXX-XXXX-XXXX format")
    device_id: Optional[str] = Field(
        default=None,
        description="Optional device identifier for device-based activation tracking",
    )


class ActivateResponse(BaseModel):
    """Response for a successful activation."""

    id: str
    tier: LicenseTier
    status: LicenseStatus
    activated_at: datetime
    expired_at: Optional[datetime]

    model_config = {"from_attributes": True}
