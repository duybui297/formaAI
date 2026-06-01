"""Schema-level tests for license tables (TASK-1.1).

Tests use SQLAlchemy ORM metadata introspection — no live Postgres required.
The in-memory SQLite engine from conftest.py creates all tables via Base.metadata.

Verification commands (featurelist.json):
  1.1-b: pytest tests/db/test_license_schema.py -k unique_keyhash_and_enums -q
  1.1-c: pytest tests/db/test_license_schema.py -k composite_index -q
  1.1-d: pytest tests/db/test_license_schema.py -k foreign_keys -q
"""
from __future__ import annotations

import sqlalchemy as sa
import pytest

from app.db.models import License, LicenseActivity, LicenseTier, LicenseStatus


# ---------------------------------------------------------------------------
# 1.1-b: UNIQUE constraint on key_hash; tier and status are SA Enum types
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_unique_keyhash_and_enums() -> None:
    """licenses.key_hash is UNIQUE; tier and status columns are SA Enum types."""
    table = License.__table__

    # --- UNIQUE on key_hash ---
    key_hash_col = table.columns["key_hash"]
    # mapped_column(unique=True) sets column.unique = True
    assert key_hash_col.unique is True, (
        "licenses.key_hash must have unique=True on the column"
    )

    # Also verify via UniqueConstraint / Index — belt-and-suspenders
    unique_cols: set[str] = set()
    for constraint in table.constraints:
        if isinstance(constraint, sa.UniqueConstraint):
            for col in constraint.columns:
                unique_cols.add(col.name)
    for idx in table.indexes:
        if idx.unique:
            for col in idx.columns:
                unique_cols.add(col.name)
    assert "key_hash" in unique_cols, (
        "key_hash must appear in a UNIQUE constraint or unique index"
    )

    # --- tier is SA Enum ---
    tier_col = table.columns["tier"]
    assert isinstance(tier_col.type, sa.Enum), (
        f"licenses.tier must be SA Enum, got {type(tier_col.type)}"
    )
    # Enum values match the Python enum
    assert set(tier_col.type.enums) == {t.value for t in LicenseTier}

    # --- status is SA Enum ---
    status_col = table.columns["status"]
    assert isinstance(status_col.type, sa.Enum), (
        f"licenses.status must be SA Enum, got {type(status_col.type)}"
    )
    assert set(status_col.type.enums) == {s.value for s in LicenseStatus}


# ---------------------------------------------------------------------------
# 1.1-c: composite index on (status, expired_at)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_composite_index() -> None:
    """licenses table has a composite index covering (status, expired_at)."""
    table = License.__table__

    matching_indexes = [
        idx for idx in table.indexes
        if set(col.name for col in idx.columns) == {"status", "expired_at"}
    ]
    assert len(matching_indexes) >= 1, (
        "licenses must have an index on (status, expired_at); "
        f"found indexes: {[idx.name for idx in table.indexes]}"
    )
    # Confirm both columns appear (ordering doesn't matter for existence check)
    idx = matching_indexes[0]
    col_names = [col.name for col in idx.columns]
    assert "status" in col_names
    assert "expired_at" in col_names


# ---------------------------------------------------------------------------
# 1.1-d: foreign keys on customer_id and license_activities.license_id
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_foreign_keys() -> None:
    """licenses.customer_id FK → users.id; license_activities.license_id FK → licenses.id."""
    licenses_table = License.__table__
    activities_table = LicenseActivity.__table__

    # --- licenses.customer_id → users.id ---
    customer_fks = {
        fk.target_fullname
        for fk in licenses_table.columns["customer_id"].foreign_keys
    }
    assert "users.id" in customer_fks, (
        f"licenses.customer_id must FK to users.id; found: {customer_fks}"
    )

    # --- license_activities.license_id → licenses.id ---
    license_fks = {
        fk.target_fullname
        for fk in activities_table.columns["license_id"].foreign_keys
    }
    assert "licenses.id" in license_fks, (
        f"license_activities.license_id must FK to licenses.id; found: {license_fks}"
    )
