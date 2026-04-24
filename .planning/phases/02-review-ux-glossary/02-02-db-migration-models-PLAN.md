---
phase: 02-review-ux-glossary
plan: "02"
type: execute
wave: 0
depends_on: []
files_modified:
  - backend/src/app/db/models.py
  - backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py
  - backend/src/app/core/config.py
autonomous: true
requirements:
  - GLOS-01
  - GLOS-02
  - GLOS-03
  - GLOS-04
  - REV-02
  - REV-03
  - REV-05
  - LAYOUT-01

must_haves:
  truths:
    - "Alembic upgrade head creates glossaries, glossary_terms, segment_flags tables in Postgres"
    - "Segment model has edited_text and expansion_ratio columns"
    - "Job model has glossary_id FK column referencing glossaries(id) ON DELETE SET NULL"
    - "Settings has expansion_ratio_thresholds field with JSON string default and expansion_thresholds_dict property"
    - "Alembic downgrade base removes all Phase 2 tables and columns cleanly"
    - "All existing unit tests still pass against SQLite (native_enum=False for new enums)"
  artifacts:
    - path: "backend/src/app/db/models.py"
      provides: "Glossary, GlossaryTerm, SegmentFlag ORM models + column extensions"
      exports: ["Glossary", "GlossaryTerm", "SegmentFlag", "FlagType", "FlagSeverity"]
    - path: "backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py"
      provides: "Alembic migration for Phase 2 schema"
      contains: "upgrade"
    - path: "backend/src/app/core/config.py"
      provides: "expansion_ratio_thresholds setting"
      contains: "expansion_ratio_thresholds"
  key_links:
    - from: "backend/src/app/db/models.py Glossary"
      to: "backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py"
      via: "Alembic upgrade head"
      pattern: "create_table.*glossaries"
    - from: "backend/src/app/core/config.py expansion_thresholds_dict"
      to: "backend/src/app/workers/translate_worker.py"
      via: "ctx['settings'].expansion_thresholds_dict"
      pattern: "expansion_thresholds_dict"
---

<objective>
Extend the database schema and ORM models for Phase 2: add Glossary, GlossaryTerm, SegmentFlag tables, extend Job with glossary_id FK, extend Segment with edited_text + expansion_ratio, and add the expansion_ratio_thresholds config field. Alembic migration covers all changes in one file.

Purpose: Every backend feature plan in Wave 1 (Plans 03 and 04) depends on these models and the migration existing. This plan can run in parallel with Plan 01 (different files).
Output: Three new ORM models, one Alembic migration, one config field. SQLite-compatible via native_enum=False.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-RESEARCH.md
@.planning/phases/02-review-ux-glossary/02-PATTERNS.md

<interfaces>
<!-- From backend/src/app/db/models.py (current) -->
```python
class Base(DeclarativeBase): pass
class JobStatus(str, enum.Enum): queued / running / needs_review / failed / done
class Job(Base):
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # ... tracked_changes_action is the last column before created_at
    # Phase 2 adds: glossary_id FK after tracked_changes_action
class Segment(Base):
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 2 adds: edited_text, expansion_ratio after translated_text
```

<!-- From backend/src/app/db/migrations/versions/e0e8f781ec72_init.py -->
```python
# Revision pattern:
revision: str = 'e0e8f781ec72'
down_revision: Union[str, None] = None
# Phase 2 migration: down_revision = 'e0e8f781ec72' (or the actual first migration ID)
```

<!-- From RESEARCH.md Section 6 — exact migration DDL -->
# Use native_enum=False for SQLite test compat — no separate PostgreSQL TYPE created
# FlagType enum values: overflow, glossary_violation, placeholder_mismatch, llm_refusal
# FlagSeverity enum values: info, warn, block
# segment_flags composite index: (segment_id, flag_type)
# glossary_terms unique constraint: (glossary_id, source_term)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend models.py with Phase 2 ORM models</name>
  <files>
    backend/src/app/db/models.py
  </files>
  <read_first>
    - backend/src/app/db/models.py (full file — add after existing Segment class)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-01 (two-table schema), D-02-03 (unique constraint), D-02-09 (segment_flags schema)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §backend/src/app/db/models.py (exact pattern + deviation notes)
  </read_first>
  <behavior>
    - FlagType enum: overflow, glossary_violation, placeholder_mismatch, llm_refusal
    - FlagSeverity enum: info, warn, block
    - Glossary model: id String(36), name String(255), source_lang String(64), target_lang String(64), timestamps, relationship to GlossaryTerm
    - GlossaryTerm model: id String(36), glossary_id FK CASCADE, source_term Text, target_term Text, notes Text nullable, created_at; UniqueConstraint(glossary_id, source_term)
    - SegmentFlag model: id String(36), segment_id String(16) FK CASCADE, flag_type SAEnum(FlagType), severity SAEnum(FlagSeverity), details JSON, created_at; Index(segment_id, flag_type)
    - Job.glossary_id: String(36) FK glossaries.id ON DELETE SET NULL, nullable=True
    - Segment.edited_text: Text, nullable=True
    - Segment.expansion_ratio: Float, nullable=True
  </behavior>
  <action>
Extend `backend/src/app/db/models.py`:

1. Add to imports (extend existing import line):
   ```python
   from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
   ```
   Also add `Float, JSON, Index, UniqueConstraint` if not present.

2. Add new enums after existing `TrackedChangesAction` enum:
   ```python
   class FlagType(str, enum.Enum):
       overflow = "overflow"
       glossary_violation = "glossary_violation"
       placeholder_mismatch = "placeholder_mismatch"
       llm_refusal = "llm_refusal"

   class FlagSeverity(str, enum.Enum):
       info = "info"
       warn = "warn"
       block = "block"
   ```

3. Add to `Job` model after `tracked_changes_action` column (before `created_at`):
   ```python
   # D-02-26: glossary locked at job submit; ON DELETE SET NULL so glossary can be deleted
   glossary_id: Mapped[str | None] = mapped_column(
       String(36),
       ForeignKey("glossaries.id", ondelete="SET NULL"),
       nullable=True,
   )
   ```

4. Add to `Segment` model after `translated_text` column:
   ```python
   # D-02-18/D-02-20: user's inline edit, persisted by PATCH /segments/{id}
   edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
   # D-02-11/LAYOUT-01: len(target)/len(source) per segment, nullable until translated
   expansion_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
   ```

5. Add `flags` relationship to `Segment`:
   ```python
   flags: Mapped[list["SegmentFlag"]] = relationship(
       "SegmentFlag", back_populates="segment", lazy="selectin"
   )
   ```

6. Add new models after `Segment` class:
   ```python
   class Glossary(Base):
       __tablename__ = "glossaries"

       id: Mapped[str] = mapped_column(
           String(36), primary_key=True, default=lambda: str(uuid.uuid4())
       )
       name: Mapped[str] = mapped_column(String(255), nullable=False)
       source_lang: Mapped[str] = mapped_column(String(64), nullable=False)
       target_lang: Mapped[str] = mapped_column(String(64), nullable=False)
       created_at: Mapped[datetime] = mapped_column(
           DateTime(timezone=True), server_default=func.now(), nullable=False
       )
       updated_at: Mapped[datetime] = mapped_column(
           DateTime(timezone=True),
           server_default=func.now(),
           onupdate=func.now(),
           nullable=False,
       )

       terms: Mapped[list["GlossaryTerm"]] = relationship(
           "GlossaryTerm", back_populates="glossary", lazy="selectin", cascade="all, delete-orphan"
       )


   class GlossaryTerm(Base):
       __tablename__ = "glossary_terms"
       __table_args__ = (
           UniqueConstraint("glossary_id", "source_term", name="uq_glossary_terms_source"),
       )

       id: Mapped[str] = mapped_column(
           String(36), primary_key=True, default=lambda: str(uuid.uuid4())
       )
       glossary_id: Mapped[str] = mapped_column(
           String(36),
           ForeignKey("glossaries.id", ondelete="CASCADE"),
           nullable=False,
           index=True,
       )
       source_term: Mapped[str] = mapped_column(Text, nullable=False)
       target_term: Mapped[str] = mapped_column(Text, nullable=False)
       notes: Mapped[str | None] = mapped_column(Text, nullable=True)
       created_at: Mapped[datetime] = mapped_column(
           DateTime(timezone=True), server_default=func.now(), nullable=False
       )

       glossary: Mapped["Glossary"] = relationship("Glossary", back_populates="terms")


   class SegmentFlag(Base):
       __tablename__ = "segment_flags"
       __table_args__ = (
           Index("ix_segment_flags_segment_flag", "segment_id", "flag_type"),
       )

       id: Mapped[str] = mapped_column(
           String(36), primary_key=True, default=lambda: str(uuid.uuid4())
       )
       segment_id: Mapped[str] = mapped_column(
           String(16),
           ForeignKey("segments.id", ondelete="CASCADE"),
           nullable=False,
       )
       # D-02-09: native_enum=False for SQLite compat in unit tests
       flag_type: Mapped[FlagType] = mapped_column(
           SAEnum(FlagType, native_enum=False), nullable=False
       )
       severity: Mapped[FlagSeverity] = mapped_column(
           SAEnum(FlagSeverity, native_enum=False), nullable=False
       )
       # D-02-08: details = {"term": source_term, "expected": target_term} for violations
       details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
       created_at: Mapped[datetime] = mapped_column(
           DateTime(timezone=True), server_default=func.now(), nullable=False
       )

       segment: Mapped["Segment"] = relationship("Segment", back_populates="flags")
   ```

CRITICAL:
- Use `JSON` (not `postgresql.JSONB`) — SQLite compat for unit tests
- Use `native_enum=False` on SAEnum for FlagType and FlagSeverity — avoids PostgreSQL TYPE creation (RESEARCH.md Pitfall 3)
- Do NOT change existing Job or Segment column definitions — only add new columns
- The `Segment` model needs a back_populates for `flags` relationship too
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend python -c "from app.db.models import Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity; print('models OK')"</automated>
  </verify>
  <done>
    - models.py imports cleanly (no ImportError)
    - Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity all importable
    - Job.glossary_id column present (nullable FK)
    - Segment.edited_text and Segment.expansion_ratio columns present
    - SegmentFlag uses native_enum=False on both SAEnum columns
    - `uv run pytest backend/tests/ -m "not integration" -x -q` still green (SQLite compat confirmed)
  </done>
</task>

<task type="auto">
  <name>Task 2: Hand-write Alembic migration 0002_phase2_glossary_flags.py</name>
  <files>
    backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py
  </files>
  <read_first>
    - backend/src/app/db/migrations/versions/ (list files — identify the current head migration ID)
    - backend/src/app/db/migrations/versions/e0e8f781ec72_init.py (or equivalent — read revision + down_revision pattern)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 6 (migration DDL template: native_enum=False, composite indexes, UniqueConstraint)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-01 (glossaries schema), D-02-03 (unique constraint), D-02-09 (segment_flags schema), D-02-11 (expansion_ratio), D-02-26 (glossary_id FK ON DELETE SET NULL)
  </read_first>
  <action>
**Step 0: Determine the current Alembic head revision**

Run this command first and record the output:
```bash
uv run --directory backend alembic heads
```
The output will show the current head revision ID (e.g., `e0e8f781ec72 (head)`).

Use that revision ID as the `down_revision` value in the migration below.

**Step 1: Hand-write the migration file**

Do NOT use `alembic revision --autogenerate` — autogenerate misses `native_enum=False`, composite
indexes, and `UniqueConstraint` with explicit names. Write the migration by hand using the DDL
template from RESEARCH.md §Section 6.

Create `backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py`:

```python
"""Phase 2: glossaries, glossary_terms, segment_flags + column additions.

Adds:
  - glossaries table (GLOS-01, D-02-01)
  - glossary_terms table with UniqueConstraint(glossary_id, source_term) (D-02-03)
  - segment_flags table with composite index(segment_id, flag_type) (D-02-09, D-02-10)
  - jobs.glossary_id FK → glossaries.id ON DELETE SET NULL (D-02-26)
  - segments.edited_text TEXT nullable (D-02-18/D-02-20)
  - segments.expansion_ratio FLOAT nullable (D-02-11, LAYOUT-01)

All SAEnum columns use native_enum=False for SQLite compat in unit tests (RESEARCH Pitfall 3).
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

# ← FILL IN: replace with output of `alembic heads` before running
revision: str = "0002_phase2"
down_revision: Union[str, None] = "REPLACE_WITH_ALEMBIC_HEADS_OUTPUT"
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
        sa.Column("flag_severity", flag_severity_enum, nullable=False),
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
```

**CRITICAL — down_revision:**
Replace `"REPLACE_WITH_ALEMBIC_HEADS_OUTPUT"` with the actual revision ID from `alembic heads`
output in Step 0. The migration will fail at apply-time (not silently) if this is wrong, but
using the correct ID from the start avoids the error.

Also verify the `severity` column name matches the model: the ORM model uses `severity` (not
`flag_severity`). Adjust the column name in create_table if the ORM column is `severity`.
Read `backend/src/app/db/models.py` Task 1 output to confirm before writing the file.

**Sanity-check grep after writing:**
```bash
grep -q "native_enum=False" backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && echo "native_enum OK"
grep -q "uq_glossary_terms_source" backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && echo "UniqueConstraint OK"
grep -q "ix_segment_flags_segment_flag" backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && echo "composite index OK"
```
  </action>
  <verify>
    <automated>grep -q "native_enum=False" /home/thu/dev/projects/ai-translation/backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && grep -q "uq_glossary_terms_source" /home/thu/dev/projects/ai-translation/backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && grep -q "def upgrade" /home/thu/dev/projects/ai-translation/backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && grep -q "def downgrade" /home/thu/dev/projects/ai-translation/backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && echo "migration OK"</automated>
  </verify>
  <done>
    - Migration file exists with correct down_revision pointing to current head (verified via alembic heads first)
    - `native_enum=False` present on both flag enums (grep confirms)
    - `uq_glossary_terms_source` UniqueConstraint present (grep confirms)
    - `ix_segment_flags_segment_flag` composite index present (grep confirms)
    - `def upgrade` and `def downgrade` both present
    - `uv run alembic upgrade head` succeeds against Postgres (creates all 3 new tables + 3 column adds)
    - `uv run alembic downgrade -1 && uv run alembic upgrade head` round-trip succeeds
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extend config.py with expansion_ratio_thresholds + startup validator</name>
  <files>
    backend/src/app/core/config.py
  </files>
  <read_first>
    - backend/src/app/core/config.py (full file — add after worker_concurrency field)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-12 (threshold env var format)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §backend/src/app/core/config.py (exact pattern)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 5 (expansion_thresholds_dict property)
  </read_first>
  <behavior>
    - Settings.expansion_ratio_thresholds is a str with default JSON: `'{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}'`
    - Settings.expansion_thresholds_dict is a @property that returns dict[str, float]
    - Settings.expansion_thresholds_dict("en->vi") returns 1.3
    - Settings.expansion_thresholds_dict("xx->yy") raises KeyError (unknown pair)
    - Custom JSON via EXPANSION_RATIO_THRESHOLDS env var overrides the default
    - Malformed EXPANSION_RATIO_THRESHOLDS env var raises ValidationError at Settings() construction (fail-fast startup)
  </behavior>
  <action>
Add to `backend/src/app/core/config.py` after the `worker_concurrency` field (before any existing `@field_validator`):

```python
    # D-02-12: per-language-pair expansion ratio thresholds (LAYOUT-01)
    # JSON string env var: EXPANSION_RATIO_THRESHOLDS
    # Format: {"src->tgt": float, ...} e.g. {"en->vi": 1.3, "vi->en": 0.9}
    # Default values tuned empirically; override via env without code change.
    expansion_ratio_thresholds: str = Field(
        default='{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}',
        description="JSON map of 'src->tgt' to float expansion ratio threshold. Default 1.5 if pair absent.",
    )
```

Also add a `@field_validator` for startup-time validation (T-02-02-01: fail fast on malformed JSON
so app refuses to start with clear error rather than crashing at property-access time):

```python
    @field_validator("expansion_ratio_thresholds")
    @classmethod
    def validate_expansion_thresholds_json(cls, v: str) -> str:
        """T-02-02-01: Validate JSON at startup — fail fast rather than at property access."""
        import json
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"EXPANSION_RATIO_THRESHOLDS must be valid JSON: {e}"
            ) from e
        if not isinstance(parsed, dict):
            raise ValueError("EXPANSION_RATIO_THRESHOLDS must be a JSON object (dict)")
        for k, val in parsed.items():
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"EXPANSION_RATIO_THRESHOLDS: value for '{k}' must be a number, got {type(val).__name__}"
                )
        return v
```

And add the `@property` accessor below the field definition:

```python
    @property
    def expansion_thresholds_dict(self) -> dict[str, float]:
        import json
        return json.loads(self.expansion_ratio_thresholds)
```

Also ensure `from pydantic import Field, field_validator` is in the imports (check existing imports
and add `field_validator` if not already present — it may already be there from Phase 1 validators).
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend python -c "from app.core.config import Settings; import os; os.environ['DASHSCOPE_API_KEY']='sk-test'; os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'; s=Settings(); d=s.expansion_thresholds_dict; assert d['en->vi'] == 1.3 and d['vi->en'] == 0.9; print('config OK')"</automated>
  </verify>
  <done>
    - `Settings().expansion_thresholds_dict` returns dict[str, float] with default values
    - `Settings().expansion_thresholds_dict["en->vi"]` == 1.3
    - `Settings().expansion_thresholds_dict["vi->en"]` == 0.9
    - `Settings(expansion_ratio_thresholds='not json')` raises pydantic.ValidationError (startup fail-fast)
    - `uv run pytest backend/tests/ -m "not integration" -x -q` still green
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| env var → Settings | EXPANSION_RATIO_THRESHOLDS is user-supplied JSON; parsed at startup |
| Alembic migration → Postgres | DDL executed with full DB credentials during upgrade |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-02-01 | Tampering | expansion_ratio_thresholds env var | mitigate | `@field_validator` on `expansion_ratio_thresholds` validates JSON shape at `Settings()` construction — app refuses to start with a clear `ValidationError` if value is malformed. Prevents silent JSONDecodeError at property-access time. |
| T-02-02-02 | Information Disclosure | SegmentFlag.details JSON column | accept | Details field stores `{"term": source_term, "expected": target_term}` — no PII; internal glossary metadata only |
| T-02-02-03 | Tampering | Alembic migration chaining | accept | down_revision must match actual head (Step 0 in Task 2 resolves this explicitly); mismatch raises alembic.util.exc.CommandError at upgrade time — not a silent failure |
</threat_model>

<verification>
After all tasks in this plan:

1. `python -c "from app.db.models import Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity; print('OK')"` — exits 0
2. `uv run alembic upgrade head` — applies cleanly to Postgres
3. `uv run alembic downgrade -1 && uv run alembic upgrade head` — round-trip clean
4. `python -c "from app.core.config import Settings; s=Settings(); assert s.expansion_thresholds_dict['en->vi'] == 1.3"` — exits 0
5. `grep -q "native_enum=False" backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py` — exits 0
6. `uv run pytest backend/tests/ -m "not integration" -x -q` — all existing tests still pass
</verification>

<success_criteria>
- models.py exports Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity
- Job model has glossary_id FK column (nullable, ON DELETE SET NULL)
- Segment model has edited_text (Text, nullable) and expansion_ratio (Float, nullable)
- SegmentFlag uses native_enum=False for SQLite compat
- Migration file 0002_phase2_glossary_flags.py: hand-written, down_revision set from alembic heads, native_enum=False, UniqueConstraint, composite index — all present
- Config has expansion_ratio_thresholds field + expansion_thresholds_dict property + @field_validator for startup JSON validation (T-02-02-01)
- All 131+ existing unit tests still pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-02-SUMMARY.md`
</output>
