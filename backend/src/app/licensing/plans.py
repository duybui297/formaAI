"""Plan → tier mapping for self-serve checkout (TASK-3.3).

Single source of truth: plan key → (LicenseTier, max_devices, validity_days).
Also defines per-tier ENTITLEMENTS (TASK-3.7) used for enforcement on /upload.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from app.db.models import LicenseTier


@dataclass(frozen=True)
class PlanConfig:
    tier: LicenseTier
    max_devices: int
    validity_days: int


# ---------------------------------------------------------------------------
# TASK-3.7: Per-tier entitlements — enforced on the upload path.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TierEntitlement:
    """Enforcement limits for a license tier."""
    max_file_bytes: int
    monthly_quota: int | None   # None = unlimited
    ocr_allowed: bool
    glossary_allowed: bool


# Single source of truth — referenced by resolver, upload route, and tests.
ENTITLEMENTS: dict[LicenseTier, TierEntitlement] = {
    LicenseTier.TRIAL: TierEntitlement(
        max_file_bytes=5 * 1024 * 1024,   # 5 MB
        monthly_quota=10,
        ocr_allowed=False,
        glossary_allowed=False,
    ),
    LicenseTier.PRO: TierEntitlement(
        max_file_bytes=50 * 1024 * 1024,  # 50 MB
        monthly_quota=None,               # unlimited
        ocr_allowed=True,
        glossary_allowed=True,
    ),
    LicenseTier.ENTERPRISE: TierEntitlement(
        max_file_bytes=100 * 1024 * 1024, # 100 MB
        monthly_quota=None,               # unlimited
        ocr_allowed=True,
        glossary_allowed=True,
    ),
}

# Tier precedence for "highest tier wins" resolver — higher index = higher tier.
_TIER_RANK: dict[LicenseTier, int] = {
    LicenseTier.TRIAL: 0,
    LicenseTier.PRO: 1,
    LicenseTier.ENTERPRISE: 2,
}


# All lowercase plan keys — match what the checkout request accepts.
PLAN_CONFIGS: Dict[str, PlanConfig] = {
    "free": PlanConfig(
        tier=LicenseTier.TRIAL,
        max_devices=1,
        validity_days=14,
    ),
    "pro": PlanConfig(
        tier=LicenseTier.PRO,
        max_devices=3,
        validity_days=365,
    ),
    "business": PlanConfig(
        tier=LicenseTier.ENTERPRISE,
        max_devices=10,
        validity_days=365,
    ),
}

VALID_PLANS = set(PLAN_CONFIGS.keys())


def get_entitlement(tier: LicenseTier) -> TierEntitlement:
    """Return entitlement for a tier."""
    return ENTITLEMENTS[tier]


# Tier → feature list for the activate response (TASK-3.5-c).
# Returned as `features: list[str]` in ActivateResponse so the FE can
# render them without a second API call.
TIER_FEATURES: dict[str, list[str]] = {
    "TRIAL": [
        "Document translation (DOCX, PDF, PPTX)",
        "Up to 1 device",
        "14-day validity",
    ],
    "PRO": [
        "Document translation (DOCX, PDF, PPTX)",
        "Up to 3 devices",
        "Glossary / terminology support",
        "365-day validity",
    ],
    "ENTERPRISE": [
        "Document translation (DOCX, PDF, PPTX)",
        "Up to 10 devices",
        "Glossary / terminology support",
        "Priority processing",
        "365-day validity",
    ],
}


def get_tier_features(tier_value: str) -> list[str]:
    """Return features for a tier value (case-insensitive lookup)."""
    return TIER_FEATURES.get(tier_value.upper(), [])


def get_plan_config(plan: str) -> PlanConfig:
    """Return the PlanConfig for *plan*, or raise ValueError for unknown plans."""
    try:
        return PLAN_CONFIGS[plan.lower()]
    except KeyError:
        raise ValueError(f"Unknown plan '{plan}'. Valid plans: {sorted(VALID_PLANS)}")
