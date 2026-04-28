"""Phase 4 fix: Add low_confidence_pages column to jobs table.

Adds:
  - jobs.low_confidence_pages: JSON nullable

WR-02: low_confidence_pages was only emitted in the Redis SSE payload during the
active worker run. After page reload the banner would never appear. Persisting the
column on the Job row makes it available via GET /jobs/{id} at any time.
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_job_low_confidence_pages"
down_revision: Union[str, None] = "0006_phase4_ocr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("low_confidence_pages", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "low_confidence_pages")
