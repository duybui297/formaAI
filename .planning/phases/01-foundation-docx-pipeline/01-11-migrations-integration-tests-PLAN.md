---
phase: 01-foundation-docx-pipeline
plan: 11
type: execute
wave: 3
depends_on:
  - "02"
files_modified:
  - backend/src/app/db/migrations/versions/001_initial_schema.py
  - backend/tests/integration/test_healthcheck.py
  - backend/tests/integration/test_docx_roundtrip.py
  - backend/tests/integration/test_lang_pairs.py
autonomous: true
requirements:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - INFRA-05
  - LANG-02
  - DOCX-01

must_haves:
  truths:
    - "Alembic first migration creates jobs and segments tables in PostgreSQL"
    - "Running `alembic upgrade head` against a fresh DB produces both tables with correct columns"
    - "healthcheck integration test verifies DashScope intl endpoint reachable + qwen-mt-turbo responds"
    - "healthcheck integration test verifies terminology param behavior on VN↔EN sample"
    - "DOCX round-trip test: extract segments from a programmatically built DOCX, mock-translate, reassemble, verify structure preserved"
    - "Language pair test: VN↔EN, VN↔JA, VN↔ZH, EN↔JA are all in the supported language list"
  artifacts:
    - path: "backend/src/app/db/migrations/versions/001_initial_schema.py"
      provides: "Alembic migration: jobs + segments tables matching Plan 02 ORM models"
      contains: "def upgrade"
    - path: "backend/tests/integration/test_healthcheck.py"
      provides: "INFRA-01 + INFRA-02: DashScope + terminology integration test"
      exports: [test_dashscope_reachable, test_terminology_respected]
    - path: "backend/tests/integration/test_docx_roundtrip.py"
      provides: "DOCX-01 + CORE-01: round-trip structural preservation test"
      exports: [test_docx_roundtrip_structure_preserved]
    - path: "backend/tests/integration/test_lang_pairs.py"
      provides: "LANG-02: language pair coverage test"
      exports: [test_required_lang_pairs_in_supported_list]
  key_links:
    - from: "backend/src/app/db/migrations/versions/001_initial_schema.py"
      to: "backend/src/app/db/models.py"
      via: "sa.Table definitions matching SQLAlchemy ORM models (W8: String(36) for Job.id)"
      pattern: "op.create_table"
    - from: "backend/tests/integration/test_healthcheck.py"
      to: "backend/src/app/llm/client.py"
      via: "make_llm_client(settings=settings) with real DASHSCOPE_API_KEY"
      pattern: "make_llm_client"
---

<objective>
Generate the Alembic first migration (aligned with Plan 02 ORM models) and write integration tests
covering INFRA-01/02 (DashScope health), DOCX-01 (round-trip), and LANG-02 (language pair coverage).

W8 note: Migration uses sa.String(36) for Job.id (not postgresql.UUID) — matches Plan 02 ORM model
`id: Mapped[str] = mapped_column(String(36), primary_key=True)`. This keeps unit tests SQLite-compatible.
The migration should be auto-generated from ORM models after Plan 02 is implemented; do NOT hand-write
column definitions that diverge from the models.

W10 note: All test imports use `from app.XXX` (not `from backend.src.app.XXX`) because pytest runs
from `backend/` with `src/` on the Python path.

W12 note: conftest.py comment explains why String(36) is used — preserves SQLite compat for unit tests.

Purpose: Verify the stack wires together before any UI is connected.
Output: Alembic migration + 3 integration test files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md

<interfaces>
<!-- From backend/src/app/db/models.py (Plan 02) — W8: actual ORM column types -->
```python
# Job model actual columns (Plan 02 implementation):
# id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
#   NOTE W8: String(36) NOT postgresql.UUID — migration must match
# status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), ...)
# stage: Mapped[JobStage | None] = mapped_column(SAEnum(JobStage), nullable=True)
# source_lang, target_lang: Mapped[str] = mapped_column(String(64))
# detected_lang: Mapped[str | None] = mapped_column(String(64), nullable=True)
# input_format: Mapped[str] = mapped_column(String(16))
# input_path: Mapped[str] = mapped_column(Text)
# output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
# original_filename: Mapped[str] = mapped_column(String(512))
# segments_done, segments_total, retry_count: Mapped[int] = mapped_column(Integer, default=0)
# error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
#   NOTE W8: Text NOT JSONB — migration must match
# has_tracked_changes: Mapped[bool] = mapped_column(Boolean, default=False)
# tracked_changes_action: Mapped[TrackedChangesAction | None] = mapped_column(SAEnum(...), nullable=True)
# created_at, updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)

# Segment model actual columns (Plan 02 implementation):
# id: Mapped[str] = mapped_column(String(16), primary_key=True)  — sha256 hex, NOT UUID
# seq_in_job: Mapped[int] = mapped_column(Integer)
# job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
#   NOTE W8: String(36) FK NOT postgresql.UUID FK
# source_text: Mapped[str] = mapped_column(Text)
# translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
# structural_position: Mapped[str] = mapped_column(Text)
# is_comment, is_inserted, is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
# created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)

# W8: NO current_batch column in Plan 02 model — do NOT add it to migration
# W8: NO last_message column in Plan 02 model — do NOT add it to migration
# W8: NO error_json JSONB column — Plan 02 uses error_msg TEXT
```

<!-- From backend/src/app/llm/client.py (Plan 03) — W10: correct signature -->
```python
def make_llm_client(settings: Settings) -> AsyncOpenAI:
    # W10: accepts settings object, NOT api_key string
    # base_url = settings.dashscope_base_url
    # api_key = settings.dashscope_api_key.get_secret_value()

async def translate_batch(
    client: AsyncOpenAI,
    segments: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str = "qwen-mt-turbo",
) -> list[str]: ...
```

<!-- From backend/src/app/pipeline/docx/extractor.py (Plan 04) — B3: actual signatures -->
```python
def extract_segments(doc: Document, job_id: str) -> list[Segment]:
    # B3: takes Document object (not path string), plus job_id string
    # Returns list[Segment] dataclasses

def reassemble_docx(
    doc: Document,
    segments: list[Segment],
    translated_texts: dict[str, str],  # segment_id -> translated_text
) -> None:
    # B3: mutates doc in-place, caller saves with doc.save(path)
    # Does NOT return a document or accept paths
```

<!-- From backend/src/app/api/routes/languages.py (Plan 06a) — B5: list[dict] shape -->
```python
SUPPORTED_LANGUAGES: list[dict[str, str]]
# Each entry: {"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese"}
# Must include codes: "auto", "vi", "en", "ja", "zh"
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Alembic first migration (jobs + segments tables)</name>
  <files>
    backend/src/app/db/migrations/versions/001_initial_schema.py
  </files>
  <action>
    IMPORTANT (W8): This migration MUST match the Plan 02 ORM models exactly.
    Do NOT hand-write column types that diverge from the ORM.
    The recommended approach: after Plan 02 models exist, run
    `cd backend && alembic revision --autogenerate -m "init"`
    and commit the generated file. This ensures zero schema drift.

    If writing by hand (e.g. before Plan 02 is implemented), use these types aligned with Plan 02:
    - Job.id: sa.String(36) — NOT postgresql.UUID(as_uuid=True)
    - Segment.job_id FK: sa.String(36) — NOT postgresql.UUID
    - error_msg: sa.Text — NOT postgresql.JSONB
    - NO current_batch column (not in Plan 02 model)
    - NO last_message column (not in Plan 02 model)
    - Enum columns (status, stage, tracked_changes_action): use sa.String with CHECK constraint
      OR let SQLAlchemy Alembic autogenerate handle the SA Enum type mapping

    Create the migration file:

    ```python
    """initial schema: jobs and segments tables

    Revision ID: 001
    Revises: (none — first migration)
    Create Date: 2026-04-23

    W8: Uses sa.String(36) for Job.id and Segment.job_id FK — matches Plan 02 ORM model.
    This keeps unit tests SQLite-compatible (no postgresql.UUID dependency).
    Integration tests (marked @pytest.mark.integration) use real PostgreSQL via docker-compose.
    """
    from __future__ import annotations

    from alembic import op
    import sqlalchemy as sa

    revision = "001"
    down_revision = None
    branch_labels = None
    depends_on = None


    def upgrade() -> None:
        op.create_table(
            "jobs",
            # W8: String(36) NOT postgresql.UUID — matches Plan 02 ORM model
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("stage", sa.String(20), nullable=True),
            sa.Column("source_lang", sa.String(64), nullable=False),
            sa.Column("target_lang", sa.String(64), nullable=False),
            sa.Column("detected_lang", sa.String(64), nullable=True),
            sa.Column("input_format", sa.String(16), nullable=False),
            sa.Column("input_path", sa.Text, nullable=False),
            sa.Column("output_path", sa.Text, nullable=True),
            sa.Column("original_filename", sa.String(512), nullable=False),
            sa.Column("segments_done", sa.Integer, nullable=False, server_default="0"),
            sa.Column("segments_total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
            # W8: Text NOT JSONB — matches Plan 02 ORM error_msg: Mapped[str | None] = mapped_column(Text)
            sa.Column("error_msg", sa.Text, nullable=True),
            sa.Column("has_tracked_changes", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("tracked_changes_action", sa.String(16), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )
        op.create_index("ix_jobs_status", "jobs", ["status"])
        op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

        op.create_table(
            "segments",
            # Segment.id: 16-char sha256 hex (D-06) — NOT UUID
            sa.Column("id", sa.String(16), primary_key=True),
            # W8: String(36) FK matches Job.id type
            sa.Column(
                "job_id",
                sa.String(36),
                sa.ForeignKey("jobs.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("seq_in_job", sa.Integer, nullable=False),
            sa.Column("source_text", sa.Text, nullable=False),
            sa.Column("translated_text", sa.Text, nullable=True),
            sa.Column("structural_position", sa.Text, nullable=False),
            sa.Column("is_comment", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("is_inserted", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("NOW()"),
                nullable=False,
            ),
        )
        op.create_index("ix_segments_job_id_seq", "segments", ["job_id", "seq_in_job"])


    def downgrade() -> None:
        op.drop_table("segments")
        op.drop_table("jobs")
    ```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend &amp;&amp; python -c "import ast, sys; ast.parse(open('src/app/db/migrations/versions/001_initial_schema.py').read()); print('syntax OK')"</automated>
  </verify>
  <done>
    - Migration file exists with revision="001", down_revision=None
    - upgrade() creates jobs and segments tables
    - Job.id: sa.String(36) — NOT postgresql.UUID (W8 aligned with Plan 02 ORM)
    - Segment.job_id FK: sa.String(36) — NOT postgresql.UUID (W8)
    - error_msg: sa.Text — NOT JSONB (W8)
    - NO current_batch or last_message columns (W8 — not in Plan 02 model)
    - downgrade() drops both tables in correct order
    - Python syntax valid
  </done>
</task>

<task type="auto">
  <name>Task 2: Integration tests — healthcheck, DOCX round-trip, language pairs</name>
  <files>
    backend/tests/integration/__init__.py
    backend/tests/integration/test_healthcheck.py
    backend/tests/integration/test_docx_roundtrip.py
    backend/tests/integration/test_lang_pairs.py
  </files>
  <action>
    All integration tests use `@pytest.mark.integration`. The `pyproject.toml` registers this marker.

    W10: All imports use `from app.XXX` (pytest runs from `backend/` with `src/` on path).
    W10: make_llm_client called as `make_llm_client(settings=settings)` — NOT `make_llm_client(api_key=...)`.

    1. Create `backend/tests/integration/__init__.py` (empty).

    2. Create `backend/tests/integration/test_healthcheck.py`:
       ```python
       """Integration tests: INFRA-01 + INFRA-02 — DashScope endpoint + terminology."""
       from __future__ import annotations

       import os
       import pytest


       @pytest.fixture(scope="module")
       def settings():
           """Load settings; skip if DASHSCOPE_API_KEY not set."""
           key = os.environ.get("DASHSCOPE_API_KEY", "")
           if not key:
               pytest.skip("DASHSCOPE_API_KEY not set — skipping DashScope integration tests")
           # W10: import from app.XXX not backend.src.app.XXX
           from app.core.config import Settings
           return Settings(
               dashscope_api_key=key,
               database_url="postgresql+asyncpg://placeholder",
           )


       @pytest.fixture(scope="module")
       def llm_client(settings):
           # W10: make_llm_client(settings=settings) — correct Plan 03 signature
           from app.llm.client import make_llm_client
           return make_llm_client(settings=settings)


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_dashscope_reachable_and_translates(llm_client) -> None:
           """INFRA-01: qwen-mt-turbo responds to a 1-sentence VN→EN probe."""
           from app.llm.translator import translate_batch

           result = await translate_batch(
               client=llm_client,
               segments=["Xin chào thế giới"],
               source_lang="vi",
               target_lang="en",
           )
           assert len(result) == 1, "CORE-03: must return 1 translation for 1 input"
           assert len(result[0]) > 0, "translation must not be empty"
           assert any(word in result[0].lower() for word in ["hello", "hi", "greetings", "world"]), (
               f"Expected VN→EN translation of 'Xin chào thế giới' to contain hello/world; got: {result[0]!r}"
           )


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_terminology_respected_vn_en(llm_client) -> None:
           """INFRA-02: terminology param causes qwen-mt-turbo to use the provided term."""
           from app.llm.translator import translate_batch

           glossary = {"AICore": "AICore"}  # force brand name preservation VN→EN
           result = await translate_batch(
               client=llm_client,
               segments=["Đây là sản phẩm của AICore dành cho thị trường Việt Nam."],
               source_lang="vi",
               target_lang="en",
               glossary=glossary,
           )
           assert len(result) == 1
           assert "AICore" in result[0], (
               f"Expected 'AICore' to be preserved via terminology param; got: {result[0]!r}"
           )


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_terminology_respected_vn_ja(llm_client) -> None:
           """INFRA-02: terminology param works on JA→EN pair too."""
           from app.llm.translator import translate_batch

           glossary = {"AICore": "AICore"}
           result = await translate_batch(
               client=llm_client,
               segments=["AICore はベトナムのAI企業です。"],
               source_lang="ja",
               target_lang="en",
               glossary=glossary,
           )
           assert len(result) == 1
           assert "AICore" in result[0]


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_auto_detect_source_language(llm_client) -> None:
           """INFRA-01 / D-16: auto source lang detection works."""
           from app.llm.translator import translate_batch

           result = await translate_batch(
               client=llm_client,
               segments=["日本語のテスト文章です。"],
               source_lang="auto",
               target_lang="en",
           )
           assert len(result) == 1
           assert len(result[0]) > 0
       ```

    3. Create `backend/tests/integration/test_docx_roundtrip.py`:
       ```python
       """Integration test: DOCX-01 — round-trip preserves structure."""
       from __future__ import annotations

       import tempfile
       from pathlib import Path
       import pytest
       from docx import Document


       def build_test_docx(path: Path) -> None:
           """Build a minimal DOCX with heading, bold run, and table."""
           doc = Document()
           doc.add_heading("Test Heading", level=1)
           para = doc.add_paragraph()
           run1 = para.add_run("Bold text ")
           run1.bold = True
           run2 = para.add_run("and normal text.")
           run2.bold = False
           table = doc.add_table(rows=2, cols=2)
           table.cell(0, 0).text = "Cell A1"
           table.cell(0, 1).text = "Cell B1"
           table.cell(1, 0).text = "Row 2 Cell A"
           table.cell(1, 1).text = "Row 2 Cell B"
           doc.save(str(path))


       @pytest.mark.integration
       def test_docx_roundtrip_structure_preserved() -> None:
           """DOCX-01: round-trip with mock translations preserves bold, table structure, heading.

           B3 fix: calls extract_segments(doc, job_id) and reassemble_docx(doc, segments, translated_texts)
           per Plan 04 actual signatures. reassemble_docx mutates doc in-place; caller saves.
           """
           # W10: from app.XXX not from backend.src.app.XXX
           from app.pipeline.docx.extractor import extract_segments
           from app.pipeline.docx.reassembler import reassemble_docx

           with tempfile.TemporaryDirectory() as tmpdir:
               src_path = Path(tmpdir) / "source.docx"
               out_path = Path(tmpdir) / "output.docx"
               build_test_docx(src_path)

               # B3: extract_segments takes (doc: Document, job_id: str) -> list[Segment]
               doc = Document(str(src_path))
               segments = extract_segments(doc, job_id="test-roundtrip")
               assert len(segments) >= 4, (
                   f"Expected at least 4 segments (heading + para + 4 table cells); got {len(segments)}"
               )

               # B3: mock translator — dict[segment_id -> translated_text]
               translated_texts = {seg.id: f"[TR] {seg.text}" for seg in segments}

               # B3: reassemble_docx(doc, segments, translated_texts) mutates doc in-place
               reassemble_docx(doc, segments, translated_texts)
               # Caller saves after reassembly
               doc.save(str(out_path))

               # Verify output is a valid DOCX
               result_doc = Document(str(out_path))

               # Paragraph 0 should be the heading, translated
               heading_para = result_doc.paragraphs[0]
               assert "[TR]" in heading_para.text, (
                   f"Heading not translated; text={heading_para.text!r}"
               )

               # Table should still exist with 2x2 cells
               assert len(result_doc.tables) >= 1
               tbl = result_doc.tables[0]
               assert tbl.rows[0].cells[0].text != "", "Table cell A1 should not be empty after round-trip"
               assert "[TR]" in tbl.rows[0].cells[0].text or "[TR]" in tbl.rows[0].cells[1].text, (
                   "At least one table cell should contain translated text"
               )


       @pytest.mark.integration
       def test_extract_segments_does_not_miss_table_cells() -> None:
           """CORE-01 / DOCX-02: extractor uses iter_inner_content, not doc.paragraphs.

           B3 fix: calls extract_segments(doc, job_id) per Plan 04 signature.
           """
           # W10: from app.XXX
           from app.pipeline.docx.extractor import extract_segments

           with tempfile.TemporaryDirectory() as tmpdir:
               src_path = Path(tmpdir) / "table_test.docx"
               doc = Document()
               doc.add_paragraph("Top paragraph")
               tbl = doc.add_table(rows=1, cols=2)
               tbl.cell(0, 0).text = "Table cell content"
               tbl.cell(0, 1).text = "Another cell"
               doc.save(str(src_path))

               # B3: pass Document object + job_id
               doc2 = Document(str(src_path))
               segments = extract_segments(doc2, job_id="test-table")
               texts = [seg.source_text for seg in segments]
               assert "Table cell content" in texts, (
                   "Extractor must find text inside table cells; 'Table cell content' missing"
               )
               assert "Another cell" in texts, (
                   "Extractor must find second table cell content"
               )
       ```

    4. Create `backend/tests/integration/test_lang_pairs.py`:
       ```python
       """Integration test: LANG-02 — required language pairs in supported list."""
       from __future__ import annotations

       import pytest


       REQUIRED_PAIRS = [
           ("vi", "en"),  # Vietnamese ↔ English
           ("en", "vi"),
           ("vi", "ja"),  # Vietnamese ↔ Japanese
           ("ja", "vi"),
           ("vi", "zh"),  # Vietnamese ↔ Chinese (Simplified)
           ("zh", "vi"),
           ("en", "ja"),  # English ↔ Japanese
           ("ja", "en"),
       ]


       @pytest.mark.integration
       def test_required_lang_pairs_in_supported_list() -> None:
           """LANG-02: All four required language pairs exist in the supported language list.

           B5 fix: SUPPORTED_LANGUAGES is list[dict] — iterate with lang["code"].
           W10 fix: from app.XXX not from backend.src.app.XXX.
           """
           # W10: correct import path
           from app.api.routes.languages import SUPPORTED_LANGUAGES

           # B5: SUPPORTED_LANGUAGES is list[dict[str, str]] with "code" key
           codes = {lang["code"] for lang in SUPPORTED_LANGUAGES}

           for src, tgt in REQUIRED_PAIRS:
               assert src in codes, (
                   f"Source language '{src}' missing from SUPPORTED_LANGUAGES. "
                   f"Present codes: {sorted(codes)}"
               )
               assert tgt in codes, (
                   f"Target language '{tgt}' missing from SUPPORTED_LANGUAGES. "
                   f"Present codes: {sorted(codes)}"
               )


       @pytest.mark.integration
       def test_auto_detect_in_source_options() -> None:
           """LANG-01: 'auto' is available as a source language option."""
           # W10: correct import path
           from app.api.routes.languages import SUPPORTED_LANGUAGES

           # B5: list[dict] iteration
           codes = [lang["code"] for lang in SUPPORTED_LANGUAGES]
           assert "auto" in codes, (
               "SUPPORTED_LANGUAGES must include 'auto' as a source option for D-16 auto-detection"
           )


       @pytest.mark.integration
       def test_priority_languages_present() -> None:
           """UI-SPEC: Priority languages (Recommended group) must exist."""
           # W10: correct import path
           from app.api.routes.languages import SUPPORTED_LANGUAGES

           # B5: list[dict] iteration
           codes = {lang["code"] for lang in SUPPORTED_LANGUAGES}
           priority = {"vi", "en", "ja", "zh"}
           missing = priority - codes
           assert not missing, (
               f"Priority languages missing from SUPPORTED_LANGUAGES: {missing}"
           )
       ```

    NOTE: Integration tests use `@pytest.mark.integration`. Run with:
    - `pytest -m integration tests/integration/` — all integration tests
    - `pytest -m "not integration"` — unit tests only (CI without DashScope key)
    - DOCX round-trip and lang pair tests do NOT need a DashScope key.
    - Only `test_healthcheck.py` tests skip without `DASHSCOPE_API_KEY`.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend &amp;&amp; python -m pytest tests/integration/test_lang_pairs.py --collect-only -q 2>&amp;1 | head -20</automated>
  </verify>
  <done>
    - Alembic migration exists: String(36) for Job.id and Segment.job_id FK (W8 aligned with Plan 02 ORM)
    - error_msg is Text not JSONB (W8)
    - No current_batch or last_message columns (W8 — not in Plan 02 model)
    - 3 integration test files with @pytest.mark.integration markers
    - All imports use `from app.XXX` (W10 fixed)
    - make_llm_client called as make_llm_client(settings=settings) (W10 fixed)
    - extract_segments called as extract_segments(doc, job_id="...") (B3 fixed)
    - reassemble_docx called as reassemble_docx(doc, segments, translated_texts) (B3 fixed)
    - translated_texts built as {seg.id: f"[TR] {seg.text}" for seg in segments} (B3 fixed)
    - SUPPORTED_LANGUAGES iterated with lang["code"] (B5 fixed)
    - test_healthcheck skips gracefully without DASHSCOPE_API_KEY
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Alembic migration → PostgreSQL | DDL executed against the database; migration must be idempotent-safe (run once) |
| Test fixtures → filesystem | Temporary DOCX files written to tmpdir; cleaned up automatically |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-11-01 | Tampering | Alembic downgrade drops all data | accept | downgrade() is intentional DDL rollback; production DB must have backups before running. Internal PoC risk is low. |
| T-01-11-02 | Information Disclosure | test_healthcheck sends real text to DashScope | mitigate | Assert on shape/content only (no print() of raw API response); key loaded from env not hardcoded |
</threat_model>

<verification>
1. Syntax: `cd backend && python -c "import ast; ast.parse(open('src/app/db/migrations/versions/001_initial_schema.py').read()); print('OK')"` — passes
2. Collection: `pytest tests/integration/ --collect-only -q` — shows 9+ test items
3. Lang pairs (no network): `pytest -m integration tests/integration/test_lang_pairs.py -v` — all pass
4. DOCX round-trip (no network): `pytest -m integration tests/integration/test_docx_roundtrip.py -v` — all pass
5. Healthcheck (with key): `DASHSCOPE_API_KEY=... pytest -m integration tests/integration/test_healthcheck.py -v` — all pass
6. No-key skip: `pytest -m integration tests/integration/test_healthcheck.py -v` (no env var) — all skipped, not failed
7. Schema check: `grep "postgresql.UUID" src/app/db/migrations/versions/001_initial_schema.py` — returns nothing (W8 verified)
</verification>

<success_criteria>
- Migration creates jobs + segments tables with String(36) for Job.id (not postgresql.UUID)
- error_msg is Text not JSONB; no current_batch or last_message columns
- Integration test collection: 9+ tests across 3 files
- All test imports use `from app.XXX` syntax (W10)
- make_llm_client called with settings= keyword argument (W10)
- extract_segments(doc, job_id=...) and reassemble_docx(doc, segments, translated_texts) per Plan 04 (B3)
- SUPPORTED_LANGUAGES iterated with lang["code"] (B5)
- DashScope tests skip cleanly without API key
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-11-SUMMARY.md`
</output>
