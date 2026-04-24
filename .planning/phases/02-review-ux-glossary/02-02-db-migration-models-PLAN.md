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
    <automated>grep -l "def upgrade" /home/thu/dev/projects/ai-translation/backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && grep -l "def downgrade" /home/thu/dev/projects/ai-translation/backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py && echo "migration file valid"</automated>
  </verify>
  <done>
    - Migration file exists with correct down_revision pointing to current head
    - `alembic upgrade head` succeeds against Postgres (creates all 3 new tables + 3 column adds)
    - `alembic downgrade base` + `alembic upgrade head` succeeds (round-trip clean)
    - `uv run pytest backend/tests/ -m "not integration" -x -q` still green (SQLite compat confirmed)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Extend config.py with expansion_ratio_thresholds</name>
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
  </behavior>
  <action>
Add to `backend/src/app/core/config.py` after the `worker_concurrency` field (before the `@field_validator`):

```python
    # D-02-12: per-language-pair expansion ratio thresholds (LAYOUT-01)
    # JSON string env var: EXPANSION_RATIO_THRESHOLDS
    # Format: {"src->tgt": float, ...} e.g. {"en->vi": 1.3, "vi->en": 0.9}
    # Default values tuned empirically; override via env without code change.
    expansion_ratio_thresholds: str = Field(
        default='{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}',
        description="JSON map of 'src->tgt' to float expansion ratio threshold. Default 1.5 if pair absent.",
    )

    @property
    def expansion_thresholds_dict(self) -> dict[str, float]:
        import json
        return json.loads(self.expansion_ratio_thresholds)
```

Also add `from pydantic import Field` to imports if not already present (check existing imports — `Field` may need to be added).

Verify the `Field` import: `pydantic.Field` is needed for the `description` parameter. If the existing file uses `pydantic_settings.BaseSettings` directly without `Field`, add it:
```python
from pydantic import Field, SecretStr, field_validator
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend python -c "from app.core.config import Settings; import os; os.environ['DASHSCOPE_API_KEY']='sk-test'; os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'; s=Settings(); d=s.expansion_thresholds_dict; assert d['en->vi'] == 1.3 and d['vi->en'] == 0.9; print('config OK')"</automated>
  </verify>
  <done>
    - `Settings().expansion_thresholds_dict` returns dict[str, float] with default values
    - `Settings().expansion_thresholds_dict["en->vi"]` == 1.3
    - `Settings().expansion_thresholds_dict["vi->en"]` == 0.9
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
| T-02-02-01 | Tampering | expansion_ratio_thresholds env var | mitigate | `json.loads` raises JSONDecodeError on malformed input — add @field_validator to catch at startup rather than at property access. If JSON is invalid at startup, Settings() raises ValidationError and the app refuses to start with clear message. |
| T-02-02-02 | Information Disclosure | SegmentFlag.details JSON column | accept | Details field stores `{"term": source_term, "expected": target_term}` — no PII; internal glossary metadata only |
| T-02-02-03 | Tampering | Alembic migration chaining | accept | down_revision must match actual head; mismatch raises alembic.util.exc.CommandError at upgrade time — not a silent failure |
</threat_model>

<verification>
After all tasks in this plan:

1. `python -c "from app.db.models import Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity; print('OK')"` — exits 0
2. `uv run alembic upgrade head` — applies cleanly to Postgres
3. `uv run alembic downgrade base && uv run alembic upgrade head` — round-trip clean
4. `python -c "from app.core.config import Settings; s=Settings(); assert s.expansion_thresholds_dict['en->vi'] == 1.3"` — exits 0
5. `uv run pytest backend/tests/ -m "not integration" -x -q` — all existing tests still pass
</verification>

<success_criteria>
- models.py exports Glossary, GlossaryTerm, SegmentFlag, FlagType, FlagSeverity
- Job model has glossary_id FK column (nullable, ON DELETE SET NULL)
- Segment model has edited_text (Text, nullable) and expansion_ratio (Float, nullable)
- SegmentFlag uses native_enum=False for SQLite compat
- Migration file 0002_phase2_glossary_flags.py exists with valid upgrade/downgrade
- Config has expansion_ratio_thresholds field + expansion_thresholds_dict property
- All 131+ existing unit tests still pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-02-SUMMARY.md`
</output>
