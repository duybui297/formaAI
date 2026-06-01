"""Schema-level tests for the users table (TASK-3.6).

Tests use SQLAlchemy ORM metadata introspection — no live Postgres required.
The in-memory SQLite engine from conftest.py creates all tables via Base.metadata.

Verification command (featurelist.json):
  3.6-a: pytest tests/db/test_user_schema.py -k users_deleted_at -q
"""
from __future__ import annotations

import sqlalchemy as sa
import pytest

from app.db.models import User


# ---------------------------------------------------------------------------
# 3.6-a: users.deleted_at column exists and is nullable
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_users_deleted_at() -> None:
    """users.deleted_at column exists, is DateTime(timezone=True), and is nullable."""
    table = User.__table__

    assert "deleted_at" in table.columns, (
        "users table must have a 'deleted_at' column; "
        f"found columns: {list(table.columns.keys())}"
    )

    col = table.columns["deleted_at"]

    # Must be nullable (existing rows keep NULL)
    assert col.nullable is True, (
        "users.deleted_at must be nullable (existing rows must default to NULL)"
    )

    # Must be a DateTime type
    assert isinstance(col.type, sa.DateTime), (
        f"users.deleted_at must be DateTime, got {type(col.type)}"
    )

    # Must be timezone-aware (timezone=True)
    assert col.type.timezone is True, (
        "users.deleted_at must be DateTime(timezone=True) (timestamptz)"
    )

    # Must have no server_default — NULL default, not a function
    assert col.server_default is None, (
        "users.deleted_at must default to NULL (no server_default)"
    )
