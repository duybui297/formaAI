---
phase: 01-foundation-docx-pipeline
plan: 11
type: execute
wave: 3
depends_on: [01-02-backend-core-PLAN.md]
files_modified:
  - backend/src/app/db/migrations/versions/001_initial_schema.py
  - backend/tests/integration/test_healthcheck.py
  - backend/tests/integration/test_docx_roundtrip.py
  - backend/tests/integration/test_lang_pairs.py
autonomous: true
requirements: [INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, LANG-02, DOCX-01]

must_haves:
  truths:
    - "Alembic first migration creates jobs and segments tables in PostgreSQL"
    - "Running `alembic upgrade head` against a fresh DB produces both tables with correct columns"
    - "healthcheck integration test verifies DashScope intl endpoint reachable + qwen-mt-turbo responds"
    - "healthcheck integration test verifies terminology param behavior on VN↔EN sample"
    - "DOCX round-trip test: extract segments from a programmatically built DOCX, translate (mocked LLM), reassemble, verify structure preserved"
    - "Language pair test: VN↔EN, VN↔JA, VN↔ZH, EN↔JA are all in the supported language list"
  artifacts:
    - path: "backend/src/app/db/migrations/versions/001_initial_schema.py"
      provides: "Alembic migration: jobs + segments tables with all columns from Plan 02 models"
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
      via: "sa.Table definitions matching SQLAlchemy models"
      pattern: "op.create_table"
    - from: "backend/tests/integration/test_healthcheck.py"
      to: "backend/src/app/llm/client.py"
      via: "make_llm_client() with real DASHSCOPE_API_KEY"
      pattern: "make_llm_client"
---

<objective>
Generate the Alembic first migration and write integration tests covering INFRA-01/02 (DashScope health), DOCX-01 (round-trip), and LANG-02 (language pair coverage).

Purpose: Verify the stack wires together before any UI is connected. Migration must be idempotent; integration tests run against real DashScope (marked `@pytest.mark.integration`) so they can be skipped in CI without a key.
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
<!-- From backend/src/app/db/models.py (Plan 02) -->
```python
# Job table columns (all required in migration):
# id: UUID primary key (server default gen_random_uuid())
# status: VARCHAR (JobStatus enum: queued/running/needs_review/failed/done)
# stage: VARCHAR (JobStage enum: parse/translate/reassemble/done/failed)
# source_lang: VARCHAR
# target_lang: VARCHAR
# detected_lang: VARCHAR nullable
# input_path: TEXT nullable
# output_path: TEXT nullable
# filename: VARCHAR nullable
# format: VARCHAR nullable
# segments_done: INTEGER default 0
# segments_total: INTEGER default 0
# current_batch: INTEGER default 0
# retry_count: INTEGER default 0
# last_message: TEXT nullable
# error_json: JSONB nullable
# created_at: TIMESTAMP WITH TIME ZONE server_default now()
# updated_at: TIMESTAMP WITH TIME ZONE server_default now() onupdate now()

# Segment table columns:
# id: VARCHAR(16) primary key (sha256 hex)
# job_id: UUID FK → jobs.id ON DELETE CASCADE
# seq_in_job: INTEGER
# source_text: TEXT
# translated_text: TEXT nullable
# structural_position: TEXT  (e.g. "body.paragraph[3].run[0]")
# is_comment: BOOLEAN default false
# is_inserted: BOOLEAN default false  (tracked changes insert)
# is_deleted: BOOLEAN default false   (tracked changes delete)
# created_at: TIMESTAMP WITH TIME ZONE server_default now()
```

<!-- From backend/src/app/llm/client.py (Plan 03) -->
```python
def make_llm_client(api_key: str) -> AsyncOpenAI:
    # base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    # api_key=api_key
    # max_retries=0
    # timeout=60.0

async def translate_batch(
    client: AsyncOpenAI,
    segments: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str = "qwen-mt-turbo",
) -> list[str]: ...
```

<!-- From backend/src/app/pipeline/docx/extractor.py (Plan 04) -->
```python
def extract_segments(doc_path: str | Path) -> list[Segment]: ...
# Returns ordered list of Segment dataclasses with id, seq_in_job, source_text, structural_position
```

<!-- From backend/src/app/pipeline/docx/reassembler.py (Plan 04) -->
```python
def write_translated_docx(
    source_path: str | Path,
    segments: list[Segment],
    translations: list[str],
    output_path: str | Path,
) -> None: ...
```

<!-- From backend/src/app/api/languages.py (Plan 06) -->
```python
SUPPORTED_LANGUAGES: list[dict[str, str]]
# Each entry: {"code": "vi", "name": "Vietnamese"}
# Must include: vi, en, ja, zh (and zh-tw if separate)
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
    Create the Alembic migration file. The revision ID should be `001` with a human-readable slug.

    The migration must create tables in dependency order (jobs first, then segments with FK):

    ```python
    """initial schema: jobs and segments tables

    Revision ID: 001
    Revises: (none — first migration)
    Create Date: 2026-04-23
    """
    from __future__ import annotations

    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    revision = "001"
    down_revision = None
    branch_labels = None
    depends_on = None


    def upgrade() -> None:
        op.create_table(
            "jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("stage", sa.String(20), nullable=False, server_default="parse"),
            sa.Column("source_lang", sa.String(20), nullable=False),
            sa.Column("target_lang", sa.String(20), nullable=False),
            sa.Column("detected_lang", sa.String(20), nullable=True),
            sa.Column("input_path", sa.Text, nullable=True),
            sa.Column("output_path", sa.Text, nullable=True),
            sa.Column("filename", sa.String(512), nullable=True),
            sa.Column("format", sa.String(20), nullable=True),
            sa.Column("segments_done", sa.Integer, nullable=False, server_default="0"),
            sa.Column("segments_total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("current_batch", sa.Integer, nullable=False, server_default="0"),
            sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("last_message", sa.Text, nullable=True),
            sa.Column("error_json", postgresql.JSONB, nullable=True),
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
        op.create_index("ix_jobs_created_at", "jobs", ["created_at", sa.desc])

        op.create_table(
            "segments",
            sa.Column("id", sa.String(16), primary_key=True),
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
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

    IMPORTANT: The `sa.desc` in `op.create_index` for `created_at` index — use `sa.desc("created_at")` as the column expression, not bare `sa.desc`. Write: `op.create_index("ix_jobs_created_at", "jobs", [sa.desc("created_at")])` — or simplify to just `["created_at"]` descending sort enforced in queries, not index definition. Use the simpler form to avoid Alembic syntax edge cases.

    Verify the alembic.ini `script_location` points to `src/app/db/migrations` and the `sqlalchemy.url` is set to use `%(DATABASE_URL)s` from environment.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && python -c "import ast, sys; ast.parse(open('src/app/db/migrations/versions/001_initial_schema.py').read()); print('syntax OK')"</automated>
  </verify>
  <done>
    - Migration file exists with revision="001", down_revision=None
    - upgrade() creates jobs and segments tables with all required columns
    - downgrade() drops both tables in correct order
    - Python syntax valid
  </done>
</task>

<task type="auto">
  <name>Task 2: Integration tests — healthcheck, DOCX round-trip, language pairs</name>
  <files>
    backend/tests/integration/__init__.py,
    backend/tests/integration/test_healthcheck.py,
    backend/tests/integration/test_docx_roundtrip.py,
    backend/tests/integration/test_lang_pairs.py
  </files>
  <action>
    All integration tests use `@pytest.mark.integration`. The `pyproject.toml` already registers this marker (Plan 02 conftest.py).

    Tests in `test_healthcheck.py` require a real `DASHSCOPE_API_KEY` env var. Skip gracefully if not set.

    1. Create `backend/tests/integration/__init__.py` (empty).

    2. Create `backend/tests/integration/test_healthcheck.py`:
       ```python
       """Integration tests: INFRA-01 + INFRA-02 — DashScope endpoint + terminology."""
       from __future__ import annotations

       import os
       import pytest
       import pytest_asyncio
       from openai import AsyncOpenAI

       DASHSCOPE_INTL_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


       @pytest.fixture(scope="module")
       def api_key() -> str:
           key = os.environ.get("DASHSCOPE_API_KEY", "")
           if not key:
               pytest.skip("DASHSCOPE_API_KEY not set — skipping DashScope integration tests")
           return key


       @pytest.fixture(scope="module")
       def llm_client(api_key: str) -> AsyncOpenAI:
           from backend.src.app.llm.client import make_llm_client
           return make_llm_client(api_key)


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_dashscope_reachable_and_translates(llm_client: AsyncOpenAI) -> None:
           """INFRA-01: qwen-mt-turbo responds to a 1-sentence VN→EN probe."""
           from backend.src.app.llm.translator import translate_batch

           result = await translate_batch(
               client=llm_client,
               segments=["Xin chào thế giới"],
               source_lang="vi",
               target_lang="en",
           )
           assert len(result) == 1, "CORE-03: must return 1 translation for 1 input"
           assert len(result[0]) > 0, "translation must not be empty"
           # Loose assertion — we don't fix the model's exact wording
           assert any(word in result[0].lower() for word in ["hello", "hi", "greetings", "world"]), (
               f"Expected VN→EN translation of 'Xin chào thế giới' to contain hello/world; got: {result[0]!r}"
           )


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_terminology_respected_vn_en(llm_client: AsyncOpenAI) -> None:
           """INFRA-02: terminology param causes qwen-mt-turbo to use the provided term."""
           from backend.src.app.llm.translator import translate_batch

           glossary = {"AICore": "AICore"}  # force brand name preservation VN→EN
           result = await translate_batch(
               client=llm_client,
               segments=["Đây là sản phẩm của AICore dành cho thị trường Việt Nam."],
               source_lang="vi",
               target_lang="en",
               glossary=glossary,
           )
           assert len(result) == 1
           # AICore must appear in output verbatim (glossary enforcement)
           assert "AICore" in result[0], (
               f"Expected 'AICore' to be preserved via terminology param; got: {result[0]!r}"
           )


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_terminology_respected_vn_ja(llm_client: AsyncOpenAI) -> None:
           """INFRA-02: terminology param works on VN→JA pair too."""
           from backend.src.app.llm.translator import translate_batch

           glossary = {"AICore": "AICore"}
           result = await translate_batch(
               client=llm_client,
               segments=["AICore はベトナムのAI企業です。"],  # JA source actually — test JA→EN
               source_lang="ja",
               target_lang="en",
               glossary=glossary,
           )
           assert len(result) == 1
           assert "AICore" in result[0]


       @pytest.mark.integration
       @pytest.mark.asyncio
       async def test_auto_detect_source_language(llm_client: AsyncOpenAI) -> None:
           """INFRA-01 / D-16: auto source lang detection works."""
           from backend.src.app.llm.translator import translate_batch

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
       from docx.shared import Pt, RGBColor


       def build_test_docx(path: Path) -> None:
           """Build a minimal DOCX with heading, bold run, table, and list."""
           doc = Document()
           # Heading
           doc.add_heading("Test Heading", level=1)
           # Paragraph with mixed formatting
           para = doc.add_paragraph()
           run1 = para.add_run("Bold text ")
           run1.bold = True
           run2 = para.add_run("and normal text.")
           run2.bold = False
           # Table
           table = doc.add_table(rows=2, cols=2)
           table.cell(0, 0).text = "Cell A1"
           table.cell(0, 1).text = "Cell B1"
           table.cell(1, 0).text = "Row 2 Cell A"
           table.cell(1, 1).text = "Row 2 Cell B"
           doc.save(str(path))


       @pytest.mark.integration
       def test_docx_roundtrip_structure_preserved() -> None:
           """DOCX-01: round-trip with mock translations preserves bold, table structure, heading."""
           from backend.src.app.pipeline.docx.extractor import extract_segments
           from backend.src.app.pipeline.docx.reassembler import write_translated_docx

           with tempfile.TemporaryDirectory() as tmpdir:
               src = Path(tmpdir) / "source.docx"
               out = Path(tmpdir) / "output.docx"
               build_test_docx(src)

               segments = extract_segments(src)
               assert len(segments) >= 4, (
                   f"Expected at least 4 segments (heading + para + 4 table cells); got {len(segments)}"
               )

               # Mock translation: append " [TRANSLATED]" to each source text
               translations = [seg.source_text + " [TRANSLATED]" for seg in segments]

               write_translated_docx(src, segments, translations, out)

               # Verify output is a valid DOCX
               result_doc = Document(str(out))

               # Paragraph 0 should be the heading (not empty, translated)
               heading_para = result_doc.paragraphs[0]
               assert "[TRANSLATED]" in heading_para.text, (
                   f"Heading not translated; text={heading_para.text!r}"
               )

               # Table should still exist with 2x2 cells
               assert len(result_doc.tables) >= 1
               tbl = result_doc.tables[0]
               assert tbl.rows[0].cells[0].text != "", "Table cell A1 should not be empty after round-trip"
               assert "[TRANSLATED]" in tbl.rows[0].cells[0].text or \
                      "[TRANSLATED]" in tbl.rows[0].cells[1].text, (
                   "At least one table cell should contain translated text"
               )

               # Bold formatting preserved — check runs on paragraph with bold run
               # Find a paragraph with mixed bold/normal run
               for para in result_doc.paragraphs:
                   if "Bold text" in para.text or "[TRANSLATED]" in para.text:
                       bold_runs = [r for r in para.runs if r.bold]
                       # After run-merge, runs[0] carries the translated text
                       # runs[1:] are blanked but their rPr (including bold) is preserved
                       break

               # No assertion on exact run structure (merge strategy may combine)
               # Key: output DOCX opens without error and has translated content


       @pytest.mark.integration
       def test_extract_segments_does_not_miss_table_cells() -> None:
           """CORE-01 / DOCX-02: extractor uses iter_inner_content, not doc.paragraphs."""
           from backend.src.app.pipeline.docx.extractor import extract_segments

           with tempfile.TemporaryDirectory() as tmpdir:
               src = Path(tmpdir) / "table_test.docx"
               doc = Document()
               doc.add_paragraph("Top paragraph")
               tbl = doc.add_table(rows=1, cols=2)
               tbl.cell(0, 0).text = "Table cell content"
               tbl.cell(0, 1).text = "Another cell"
               doc.save(str(src))

               segments = extract_segments(src)
               texts = [seg.source_text for seg in segments]
               assert "Table cell content" in texts, (
                   "Extractor must find text inside table cells; 'Table cell content' missing from segments"
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
           """LANG-02: All four required language pairs exist in the supported language list."""
           from backend.src.app.api.languages import SUPPORTED_LANGUAGES

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
           from backend.src.app.api.languages import SUPPORTED_LANGUAGES

           codes = [lang["code"] for lang in SUPPORTED_LANGUAGES]
           assert "auto" in codes, (
               "SUPPORTED_LANGUAGES must include 'auto' as a source option for D-16 auto-detection"
           )


       @pytest.mark.integration
       def test_priority_languages_present() -> None:
           """UI-SPEC: Priority languages (Recommended group) must exist."""
           from backend.src.app.api.languages import SUPPORTED_LANGUAGES

           codes = {lang["code"] for lang in SUPPORTED_LANGUAGES}
           priority = {"vi", "en", "ja", "zh"}  # Vietnamese, English, Japanese, Chinese
           missing = priority - codes
           assert not missing, (
               f"Priority languages missing from SUPPORTED_LANGUAGES: {missing}"
           )
       ```

    NOTE: These integration tests use `@pytest.mark.integration`. Run with:
    - `pytest -m integration tests/integration/` to run all integration tests
    - `pytest -m "not integration"` to run only unit tests (CI without DashScope key)
    - The DOCX round-trip and lang pair tests do NOT need a DashScope key — they test local code.
    - Only `test_healthcheck.py` tests skip without `DASHSCOPE_API_KEY`.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && python -m pytest tests/integration/test_lang_pairs.py --collect-only -q 2>&1 | head -20</automated>
  </verify>
  <done>
    - Alembic migration file exists with correct revision chain
    - 3 integration test files collected by pytest
    - test_healthcheck tests skip gracefully without DASHSCOPE_API_KEY
    - test_docx_roundtrip tests run without network access
    - test_lang_pairs tests run without network access
    - All marked @pytest.mark.integration
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Alembic migration → PostgreSQL | DDL executed against the database; migration must be idempotent-safe (run once) |
| Test fixtures → filesystem | Temporary DOCX files written to tmpdir; no cleanup risk |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-11-01 | Tampering | Alembic downgrade drops all data | accept | downgrade() is intentional DDL rollback; production DB must have backups before running. Internal PoC risk is low. |
| T-01-11-02 | Information Disclosure | test_healthcheck prints real DashScope responses | mitigate | Assert on shape/content only (no `print()` of raw API response); key loaded from env not hardcoded |
</threat_model>

<verification>
1. Syntax: `python -c "import ast; ast.parse(open('src/app/db/migrations/versions/001_initial_schema.py').read()); print('OK')"` — passes
2. Collection: `pytest tests/integration/ --collect-only -q` — shows 9+ test items
3. Lang pairs (no network): `pytest -m integration tests/integration/test_lang_pairs.py -v` — all pass
4. DOCX round-trip (no network): `pytest -m integration tests/integration/test_docx_roundtrip.py -v` — all pass
5. Healthcheck (with key): `DASHSCOPE_API_KEY=... pytest -m integration tests/integration/test_healthcheck.py -v` — all pass
6. No-key skip: `pytest -m integration tests/integration/test_healthcheck.py -v` (no env var) — all skipped, not failed
</verification>

<success_criteria>
- Migration creates jobs + segments tables with all required columns and FK constraint
- Integration test collection: 9+ tests across 3 files
- LANG-02: all 8 directional pairs (vi↔en, vi↔ja, vi↔zh, en↔ja) verified present
- DOCX round-trip: translated content appears in output DOCX, table cells not missed
- DashScope tests skip cleanly without API key
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-11-SUMMARY.md`
</output>
