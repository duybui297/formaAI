"""Phase 2: glossaries, glossary_terms, segment_flags + column additions.

Adds:
  - glossaries table (GLOS-01, D-02-01)
  - glossary_terms table with UniqueConstraint(glossary_id, source_term) (D-02-03)
  - segment_flags table with composite index(segment_id, flag_type) (D-02-09, D-02-10)
  - jobs.glossary_id FK -> glossaries.id ON DELETE SET NULL (D-02-26)
  - segments.edited_text TEXT nullable (D-02-18/D-02-20)
  - segments.expansion_ratio FLOAT nullable (D-02-11, LAYOUT-01)

All SAEnum columns use native_enum=False for SQLite compat in unit tests (RESEARCH Pitfall 3).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase2"
down_revision: Union[str, None] = "e0e8f781ec72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # glossaries
    # ------------------------------------------------------------------
    op.create_table(
        "glossaries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_lang", sa.String(64), nullable=False),
        sa.Column("target_lang", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # glossary_terms
    # ------------------------------------------------------------------
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("glossary_id", sa.String(36), nullable=False),
        sa.Column("source_term", sa.Text, nullable=False),
        sa.Column("target_term", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["glossary_id"],
            ["glossaries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        # D-02-03: unique (glossary_id, source_term)
        sa.UniqueConstraint("glossary_id", "source_term", name="uq_glossary_terms_source"),
    )
    op.create_index("ix_glossary_terms_glossary_id", "glossary_terms", ["glossary_id"])

    # ------------------------------------------------------------------
    # segment_flags
    # D-02-09: native_enum=False (no PostgreSQL TYPE object created)
    # ------------------------------------------------------------------
    flag_type_enum = sa.Enum(
        "overflow",
        "glossary_violation",
        "placeholder_mismatch",
        "llm_refusal",
        name="flagtype",
        native_enum=False,  # VARCHAR storage; SQLite-compat
    )
    flag_severity_enum = sa.Enum(
        "info",
        "warn",
        "block",
        name="flagseverity",
        native_enum=False,  # VARCHAR storage; SQLite-compat
    )
    op.create_table(
        "segment_flags",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("segment_id", sa.String(16), nullable=False),
        sa.Column("flag_type", flag_type_enum, nullable=False),
        sa.Column("severity", flag_severity_enum, nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["segment_id"],
            ["segments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # D-02-10: composite index for flag-count GROUP BY query
    op.create_index(
        "ix_segment_flags_segment_flag",
        "segment_flags",
        ["segment_id", "flag_type"],
    )

    # ------------------------------------------------------------------
    # jobs.glossary_id (D-02-26: ON DELETE SET NULL)
    # ------------------------------------------------------------------
    op.add_column(
        "jobs",
        sa.Column("glossary_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_glossary_id",
        "jobs",
        "glossaries",
        ["glossary_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # segments.edited_text (D-02-18/D-02-20)
    # ------------------------------------------------------------------
    op.add_column(
        "segments",
        sa.Column("edited_text", sa.Text, nullable=True),
    )

    # ------------------------------------------------------------------
    # segments.expansion_ratio (D-02-11, LAYOUT-01)
    # ------------------------------------------------------------------
    op.add_column(
        "segments",
        sa.Column("expansion_ratio", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("segments", "expansion_ratio")
    op.drop_column("segments", "edited_text")
    op.drop_constraint("fk_jobs_glossary_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "glossary_id")
    op.drop_index("ix_segment_flags_segment_flag", table_name="segment_flags")
    op.drop_table("segment_flags")
    op.drop_index("ix_glossary_terms_glossary_id", table_name="glossary_terms")
    op.drop_table("glossary_terms")
    op.drop_table("glossaries")
