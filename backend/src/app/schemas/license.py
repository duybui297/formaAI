"""Pydantic schemas for license management endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.db.models import LicenseStatus, LicenseTier


class AdminCreateLicenseRequest(BaseModel):
    """Body for POST /api/admin/licenses — FE contract (TASK-2.1-e / TASK-3.1).

    Accepts FE vocab:
      tier        — "starter" | "professional" | "enterprise"
      customer_id — user EMAIL string (resolved to UUID FK by the admin route)
      max_devices — optional, default 1
      expired_at  — optional ISO date string

    Only used at the admin-API boundary.  Internal service code and the
    self-serve checkout path use InternalCreateLicenseRequest instead.
    """

    tier: str = Field(..., description="FE tier: starter | professional | enterprise")
    customer_id: str = Field(
        ...,
        description="Email address of the user who will own this license",
    )
    max_devices: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum device activations allowed (default 1 if omitted)",
    )
    expired_at: Optional[str] = Field(
        default=None,
        description="Optional fixed expiry as an ISO date/datetime string",
    )
    send_email: bool = Field(
        default=True,
        description="Send the license delivery email to the customer (default: true)",
    )

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        from app.licensing.vocab import TIER_FE_TO_BE
        if v.lower() not in TIER_FE_TO_BE:
            valid = sorted(TIER_FE_TO_BE)
            raise ValueError(f"tier must be one of {valid}, got {v!r}")
        return v.lower()

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        """Must look like an email address (contains @)."""
        if "@" not in v:
            raise ValueError("customer_id must be a valid email address")
        return v.lower().strip()

    @field_validator("expired_at")
    @classmethod
    def validate_expired_at(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("expired_at must be a valid ISO datetime string")
        return v


# Keep old name as alias so any remaining import of CreateLicenseRequest still
# resolves — the admin route was the only real user; checkout is being migrated.
CreateLicenseRequest = AdminCreateLicenseRequest


class InternalCreateLicenseRequest(BaseModel):
    """Internal-only request shape used by license_service.create_license.

    Fields are already resolved:
      tier        — BE LicenseTier enum (not FE vocab string)
      customer_id — user UUID string (not email)
      max_devices — optional, default 1
      expires_at  — optional pre-computed datetime (not a raw ISO string)

    No FE-vocab or email validators — callers are responsible for resolution
    before constructing this object.
    """

    tier: LicenseTier = Field(..., description="BE LicenseTier enum")
    customer_id: str = Field(..., description="UUID of the license owner")
    max_devices: Optional[int] = Field(default=None, gt=0)
    expires_at: Optional[datetime] = Field(default=None)


class LicenseActivityResponse(BaseModel):
    """Single audit-log entry."""

    id: str
    license_id: str
    event_type: str
    actor_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class LicenseResponse(BaseModel):
    """Response for a single license (legacy — used by older non-admin endpoints).

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
    """Response for a successful activation.

    FE contract (TASK-3.5-c / ActivateLicenseResponse in types.ts):
      tier     — lowercase tier string (e.g. "trial", "pro", "enterprise")
      status   — lowercase status string (e.g. "active")
      expiry   — ISO datetime string of expired_at, or null
      features — list[str] derived from the tier's feature set

    Legacy fields (kept for existing test assertions):
      id, activated_at, expired_at
    """

    id: str
    tier: str               # lowercase, e.g. "trial" / "pro" / "enterprise"
    status: str             # lowercase, e.g. "active"
    activated_at: datetime
    expired_at: Optional[datetime]
    # FE-contract fields
    expiry: Optional[str]   # expired_at as ISO string, or null
    features: list[str]     # derived from tier

    model_config = {"from_attributes": False}


# ---------------------------------------------------------------------------
# TASK-2.5: Admin CRUD schemas — aligned to FE contract (TASK-3.1)
# ---------------------------------------------------------------------------


def _make_key_masked(key_hash: str | None) -> str:
    """Produce key_masked in the visual form ****-****-****-XXXX.

    XXXX = last 4 characters of key_hash (SHA-256 hex).
    This is a hash suffix, not the real key tail — acceptable for admin lookup
    since the raw key is never persisted.
    """
    if key_hash and len(key_hash) >= 4:
        suffix = key_hash[-4:].upper()
    else:
        suffix = "????"
    return f"****-****-****-{suffix}"


class LicenseAdminResponse(BaseModel):
    """Response shape for a single license — matches FE License interface.

    Fields:
      key_masked  ****-****-****-XXXX where XXXX = last 4 chars of key_hash
      tier        FE vocab: starter | professional | enterprise
      status      FE lowercase: active | suspended | revoked | expired | pending
      customer_id owner email (not UUID)
      issued_at   alias for created_at (column name in DB: issued_at)
    """

    id: str
    key_masked: str
    tier: str          # FE vocab string, not BE enum
    status: str        # FE lowercase string, not BE enum
    customer_id: Optional[str]
    max_devices: int
    issued_at: datetime
    activated_at: Optional[datetime]
    expired_at: Optional[datetime]

    model_config = {"from_attributes": False}

    @classmethod
    def from_license(
        cls,
        lic: object,
        customer_email: Optional[str] = None,
    ) -> "LicenseAdminResponse":
        """Build a FE-vocab response from a License ORM row.

        Parameters
        ----------
        lic:
            SQLAlchemy License ORM instance.
        customer_email:
            Pre-resolved email for lic.customer_id.  Pass None when the email
            is unavailable — customer_id will fall back to the UUID string.
        """
        from app.licensing.vocab import be_tier_to_fe, be_status_to_fe

        be_tier = lic.tier  # type: ignore[attr-defined]
        be_status = lic.status  # type: ignore[attr-defined]

        # be_tier / be_status may be enum instances or plain strings
        if hasattr(be_tier, "value"):
            be_tier = type(lic.tier)(be_tier.value)  # type: ignore[attr-defined]
        if hasattr(be_status, "value"):
            be_status = type(lic.status)(be_status.value)  # type: ignore[attr-defined]

        # Resolve to FE vocab strings
        try:
            fe_tier = be_tier_to_fe(be_tier)  # type: ignore[arg-type]
        except KeyError:
            # Fallback: use value as-is (shouldn't happen with valid DB data)
            fe_tier = str(be_tier.value) if hasattr(be_tier, "value") else str(be_tier)

        try:
            fe_status = be_status_to_fe(be_status)  # type: ignore[arg-type]
        except KeyError:
            fe_status = str(be_status.value) if hasattr(be_status, "value") else str(be_status)

        return cls(
            id=lic.id,  # type: ignore[attr-defined]
            key_masked=_make_key_masked(lic.key_hash),  # type: ignore[attr-defined]
            tier=fe_tier,
            status=fe_status,
            customer_id=customer_email if customer_email is not None else lic.customer_id,  # type: ignore[attr-defined]
            max_devices=lic.max_devices,  # type: ignore[attr-defined]
            issued_at=lic.issued_at,  # type: ignore[attr-defined]
            activated_at=lic.activated_at,  # type: ignore[attr-defined]
            expired_at=lic.expired_at,  # type: ignore[attr-defined]
        )


# Keep legacy aliases so other code that imports LicenseDetailResponse / LicenseListItem still compiles.
LicenseDetailResponse = LicenseAdminResponse
LicenseListItem = LicenseAdminResponse


class LicenseListResponse(BaseModel):
    """Paginated envelope for GET /admin/licenses — key is 'licenses' per FE contract."""

    licenses: list[LicenseAdminResponse]
    total: int
    page: int
    page_size: int


class LicenseActivityFEResponse(BaseModel):
    """Single activity row — matches FE LicenseActivity interface.

    FE field mapping:
      action  ← event_type (string value of LicenseEventType enum)
      actor   ← actor_id (nullable)
      detail  ← None (no detail column exists; reserved for future use)
    """

    id: str
    license_id: str
    action: str
    actor: Optional[str]
    detail: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": False}

    @classmethod
    def from_activity(cls, a: object) -> "LicenseActivityFEResponse":
        event_type = a.event_type  # type: ignore[attr-defined]
        # event_type may be a LicenseEventType enum or a plain string
        action_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        return cls(
            id=a.id,  # type: ignore[attr-defined]
            license_id=a.license_id,  # type: ignore[attr-defined]
            action=action_str,
            actor=a.actor_id,  # type: ignore[attr-defined]
            detail=None,  # no detail column; reserved
            created_at=a.created_at,  # type: ignore[attr-defined]
        )


# Legacy alias used by activate_license / older imports
class LicenseActivityResponse(BaseModel):  # noqa: F811
    """Single audit-log entry (legacy — used by non-admin endpoints)."""

    id: str
    license_id: str
    event_type: str
    actor_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class BulkIdsRequest(BaseModel):
    """Body for POST /admin/licenses/suspend and POST /admin/licenses/revoke."""

    ids: list[str] = Field(..., description="License IDs to act on")


class ExtendRequest(BaseModel):
    """Body for POST /admin/licenses/{id}/extend — absolute datetime, not relative days."""

    expired_at: datetime = Field(
        ...,
        description="New absolute expiry datetime (UTC). Must be in the future.",
    )


# ---------------------------------------------------------------------------
# FE Create response — TASK-2.1-e
# ---------------------------------------------------------------------------

class FECreateLicenseResponse(BaseModel):
    """201 response for POST /admin/licenses — FE contract.

    Nested shape: { license: LicenseAdminResponse, raw_key: str | None }
    raw_key is returned exactly once (creation); None on idempotent replay.
    """

    license: LicenseAdminResponse
    raw_key: Optional[str] = None


# ---------------------------------------------------------------------------
# User license portal — TASK-2.1-g
# ---------------------------------------------------------------------------


class MyLicenseItem(BaseModel):
    """A single license owned by the current user — for GET /licenses/my-licenses.

    Unlike LicenseAdminResponse, this is intentionally lean:
      - id, tier, status, issued_at, activated_at, expired_at, max_devices
      - NO key_masked (raw key never persisted; no point showing a hash suffix)
      - NO customer_id (redundant — it's always the current user)

    status values: pending | active | expired | suspended | revoked
    """

    id: str
    tier: str          # FE vocab string: starter | professional | enterprise
    status: str        # FE lowercase: pending | active | expired | suspended | revoked
    issued_at: datetime
    activated_at: Optional[datetime]
    expired_at: Optional[datetime]
    max_devices: int

    model_config = {"from_attributes": False}

    @classmethod
    def from_license(cls, lic: object) -> "MyLicenseItem":
        from app.licensing.vocab import be_tier_to_fe, be_status_to_fe

        be_tier = lic.tier  # type: ignore[attr-defined]
        be_status = lic.status  # type: ignore[attr-defined]

        if hasattr(be_tier, "value"):
            be_tier = type(lic.tier)(be_tier.value)  # type: ignore[attr-defined]
        if hasattr(be_status, "value"):
            be_status = type(lic.status)(be_status.value)  # type: ignore[attr-defined]

        try:
            fe_tier = be_tier_to_fe(be_tier)  # type: ignore[arg-type]
        except KeyError:
            fe_tier = str(be_tier.value) if hasattr(be_tier, "value") else str(be_tier)

        try:
            fe_status = be_status_to_fe(be_status)  # type: ignore[arg-type]
        except KeyError:
            fe_status = str(be_status.value) if hasattr(be_status, "value") else str(be_status)

        return cls(
            id=lic.id,  # type: ignore[attr-defined]
            tier=fe_tier,
            status=fe_status,
            issued_at=lic.issued_at,  # type: ignore[attr-defined]
            activated_at=lic.activated_at,  # type: ignore[attr-defined]
            expired_at=lic.expired_at,  # type: ignore[attr-defined]
            max_devices=lic.max_devices,  # type: ignore[attr-defined]
        )


class MyLicensesResponse(BaseModel):
    """Paginated response for GET /licenses/my-licenses."""

    licenses: list[MyLicenseItem]
    total: int
    pending_count: int  # number of PENDING licenses (not yet activated)
