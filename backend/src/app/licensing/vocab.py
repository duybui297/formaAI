"""FE ↔ BE vocabulary mapping for license tier and status.

This module is the SINGLE source of truth for the translation between:
  - FE vocab  (what the admin dashboard sends/receives): starter / professional / enterprise
  - BE enums  (what the DB and domain logic use):        TRIAL   / PRO           / ENTERPRISE

Rules
-----
- All other backend code (activation, middleware, cron, seed) MUST keep using BE enums.
- This mapping is applied ONLY at the admin-API boundary:
    * Inbound:  FE tier/status strings → BE enums  (request decoding)
    * Outbound: BE enums → FE tier/status strings  (response serialisation)
"""
from __future__ import annotations

from app.db.models import LicenseStatus, LicenseTier

# ---------------------------------------------------------------------------
# Tier
# ---------------------------------------------------------------------------

TIER_FE_TO_BE: dict[str, LicenseTier] = {
    "starter": LicenseTier.TRIAL,
    "professional": LicenseTier.PRO,
    "enterprise": LicenseTier.ENTERPRISE,
}

TIER_BE_TO_FE: dict[LicenseTier, str] = {v: k for k, v in TIER_FE_TO_BE.items()}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

STATUS_FE_TO_BE: dict[str, LicenseStatus] = {
    "active": LicenseStatus.ACTIVE,
    "suspended": LicenseStatus.SUSPENDED,
    "revoked": LicenseStatus.REVOKED,
    "expired": LicenseStatus.EXPIRED,
    "pending": LicenseStatus.PENDING,
}

STATUS_BE_TO_FE: dict[LicenseStatus, str] = {v: k for k, v in STATUS_FE_TO_BE.items()}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def fe_tier_to_be(fe_tier: str) -> LicenseTier:
    """Convert FE tier string to BE LicenseTier enum.  Raises ValueError on unknown."""
    try:
        return TIER_FE_TO_BE[fe_tier.lower()]
    except KeyError:
        valid = sorted(TIER_FE_TO_BE)
        raise ValueError(f"Unknown FE tier {fe_tier!r}. Valid values: {valid}")


def be_tier_to_fe(be_tier: LicenseTier) -> str:
    """Convert BE LicenseTier enum to FE tier string. Returns 'unknown' for invalid values."""
    return TIER_BE_TO_FE.get(be_tier, "unknown")


def fe_status_to_be(fe_status: str) -> LicenseStatus:
    """Convert FE status string to BE LicenseStatus enum.  Raises ValueError on unknown."""
    try:
        return STATUS_FE_TO_BE[fe_status.lower()]
    except KeyError:
        valid = sorted(STATUS_FE_TO_BE)
        raise ValueError(f"Unknown FE status {fe_status!r}. Valid values: {valid}")


def be_status_to_fe(be_status: LicenseStatus) -> str:
    """Convert BE LicenseStatus enum to FE status string. Returns 'unknown' for invalid values."""
    return STATUS_BE_TO_FE.get(be_status, "unknown")
