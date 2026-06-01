"""Schema-level tests for the leads table (TASK-3.5-a).

Tests use SQLAlchemy ORM metadata introspection — no live Postgres required.
The in-memory SQLite engine creates all tables via Base.metadata.create_all.

Verification command (featurelist.json):
  3.5-a: pytest tests/db/test_leads_schema.py -k leads_table -q
"""
from __future__ import annotations

import sqlalchemy as sa
import pytest


@pytest.mark.unit
def test_leads_table() -> None:
    """leads table exists with columns: id (PK), email (str), plan (str), created_at (tz-aware)."""
    from app.db.models import Lead

    table = Lead.__table__

    assert table.name == "leads", f"Expected table name 'leads', got {table.name!r}"

    # --- id: primary key ---
    id_col = table.columns["id"]
    assert id_col.primary_key, "leads.id must be the primary key"
    assert isinstance(id_col.type, sa.String), (
        f"leads.id must be String, got {type(id_col.type)}"
    )

    # --- email: non-nullable string ---
    email_col = table.columns["email"]
    assert not email_col.nullable, "leads.email must be NOT NULL"
    assert isinstance(email_col.type, sa.String), (
        f"leads.email must be String, got {type(email_col.type)}"
    )

    # --- plan: non-nullable string ---
    plan_col = table.columns["plan"]
    assert not plan_col.nullable, "leads.plan must be NOT NULL"
    assert isinstance(plan_col.type, sa.String), (
        f"leads.plan must be String, got {type(plan_col.type)}"
    )

    # --- created_at: timezone-aware datetime with server_default ---
    created_at_col = table.columns["created_at"]
    assert not created_at_col.nullable, "leads.created_at must be NOT NULL"
    assert isinstance(created_at_col.type, sa.DateTime), (
        f"leads.created_at must be DateTime, got {type(created_at_col.type)}"
    )
    assert created_at_col.type.timezone is True, (
        "leads.created_at must be timezone=True (timestamptz)"
    )
    assert created_at_col.server_default is not None, (
        "leads.created_at must have a server_default (e.g. func.now())"
    )
