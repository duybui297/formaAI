"""Plan → tier mapping for self-serve checkout (TASK-3.3).

Single source of truth: plan key → (LicenseTier, max_devices, validity_days).
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


def get_plan_config(plan: str) -> PlanConfig:
    """Return the PlanConfig for *plan*, or raise ValueError for unknown plans."""
    try:
        return PLAN_CONFIGS[plan.lower()]
    except KeyError:
        raise ValueError(f"Unknown plan '{plan}'. Valid plans: {sorted(VALID_PLANS)}")
