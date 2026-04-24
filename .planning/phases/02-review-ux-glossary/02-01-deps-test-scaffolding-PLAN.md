---
phase: 02-review-ux-glossary
plan: "01"
type: execute
wave: 0
depends_on: []
files_modified:
  - frontend/package.json
  - frontend/tailwind.config.ts
  - frontend/src/components/ui/textarea.tsx
  - frontend/src/components/ui/input.tsx
  - frontend/src/components/ui/popover.tsx
  - frontend/src/components/ui/command.tsx
  - backend/tests/conftest.py
  - backend/tests/api/test_glossaries.py
  - backend/tests/api/test_segments.py
  - backend/tests/services/test_glossary_service.py
  - backend/tests/services/test_csv_import.py
  - backend/tests/services/test_tbx_import.py
  - backend/tests/services/test_post_check.py
  - backend/tests/services/test_export_service.py
  - backend/tests/workers/test_worker_glossary.py
  - frontend/src/__tests__/SegmentTable.test.tsx
  - frontend/src/__tests__/useSegments.test.ts
  - frontend/src/__tests__/FlagBadge.test.tsx
  - frontend/src/__tests__/GlossarySelect.test.tsx
autonomous: true
requirements:
  - GLOS-01
  - GLOS-02
  - GLOS-03
  - GLOS-04
  - REV-01
  - REV-02
  - REV-03
  - REV-04
  - REV-05
  - REV-06
  - LAYOUT-01

must_haves:
  truths:
    - "npm install succeeds with react-virtuoso and react-hotkeys-hook present in package.json"
    - "shadcn textarea, input, popover, command components exist in frontend/src/components/ui/"
    - "frontend/tailwind.config.ts has paper-ink and paper-accent color tokens"
    - "All backend Wave 0 test stub files exist and pytest can collect them"
    - "All frontend Wave 0 test stub files exist and vitest can discover them"
    - "conftest.py exports Glossary, GlossaryTerm, SegmentFlag factory fixtures for Phase 2 tests"
  artifacts:
    - path: "frontend/package.json"
      provides: "react-virtuoso + react-hotkeys-hook deps"
      contains: "react-virtuoso"
    - path: "frontend/tailwind.config.ts"
      provides: "paper-ink and paper-accent color tokens per D-02-27/28"
      contains: "paper-ink"
    - path: "backend/tests/conftest.py"
      provides: "shared fixtures"
      exports: ["make_glossary", "make_glossary_term", "make_segment_flag"]
    - path: "backend/tests/api/test_glossaries.py"
      provides: "GLOS-01/05 test stubs"
    - path: "backend/tests/services/test_post_check.py"
      provides: "GLOS-04/LAYOUT-01 test stubs"
    - path: "backend/tests/services/test_export_service.py"
      provides: "REV-05/REV-06 test stubs"
  key_links:
    - from: "conftest.py make_glossary fixture"
      to: "backend/tests/api/test_glossaries.py"
      via: "pytest fixture injection"
      pattern: "make_glossary"
    - from: "frontend/__tests__/useSegments.test.ts"
      to: "TanStack Query v5 mock"
      via: "QueryClient wrapper"
      pattern: "QueryClient"
---

<objective>
Wave 0 setup: install new npm dependencies, add shadcn components, apply paper skill tokens to tailwind.config.ts, and create all Wave 0 test stub files (both backend and frontend). No feature logic is implemented here — only infrastructure that later waves depend on.

Purpose: Every feature wave depends on test stubs existing first (Nyquist rule). npm deps and shadcn components must be installed before any frontend feature work. Paper color tokens must be in tailwind.config.ts before Phase 2 component styles reference them (D-02-27/28).
Output: Populated package.json with react-virtuoso + react-hotkeys-hook, 4 shadcn components, paper tokens in tailwind.config.ts, 8 backend test stubs, 4 frontend test stubs, expanded conftest.py fixtures.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-RESEARCH.md
@.planning/phases/02-review-ux-glossary/02-VALIDATION.md

<interfaces>
<!-- From backend/tests/conftest.py (existing) -->
```python
# Existing fixtures: test_engine (session-scoped), db_session (function-scoped), mock_redis, mock_llm_client, mock_arq_ctx
# db_session uses SQLite in-memory; Base.metadata.create_all at session start
# All Phase 2 new models (Glossary, GlossaryTerm, SegmentFlag) will appear after models.py is extended in Plan 02
```

<!-- From RESEARCH.md §Validation Architecture -->
```
Backend test framework: pytest 8.x + pytest-asyncio (asyncio_mode = "auto")
Backend quick run: uv run pytest backend/tests/ -m "not integration" -x --no-header -q
Frontend test framework: vitest 1.x + Testing Library (jsdom)
Frontend quick run: npm --prefix frontend run test
```

<!-- Wave 0 gaps from VALIDATION.md -->
New backend tests needed:
  backend/tests/api/test_glossaries.py          → GLOS-01, GLOS-05
  backend/tests/api/test_segments.py            → REV-02, REV-04
  backend/tests/services/test_glossary_service.py → GLOS-01 service layer
  backend/tests/services/test_csv_import.py     → GLOS-02 CSV
  backend/tests/services/test_tbx_import.py     → GLOS-02 TBX
  backend/tests/services/test_post_check.py     → GLOS-04, LAYOUT-01
  backend/tests/services/test_export_service.py → REV-05, REV-06
  backend/tests/workers/test_worker_glossary.py → GLOS-03

New frontend tests needed:
  frontend/src/__tests__/SegmentTable.test.tsx  → REV-01
  frontend/src/__tests__/useSegments.test.ts    → REV-02
  frontend/src/__tests__/FlagBadge.test.tsx     → REV-03
  frontend/src/__tests__/GlossarySelect.test.tsx → UPLD-04
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Install npm dependencies, shadcn components, and apply paper tokens to tailwind.config.ts</name>
  <files>
    frontend/package.json
    frontend/tailwind.config.ts
    frontend/src/components/ui/textarea.tsx
    frontend/src/components/ui/input.tsx
    frontend/src/components/ui/popover.tsx
    frontend/src/components/ui/command.tsx
  </files>
  <read_first>
    - frontend/package.json (current deps, check react-virtuoso/react-hotkeys-hook absent)
    - frontend/tailwind.config.ts (current config — extend theme.colors without replacing existing tokens)
    - frontend/src/components/ui/select.tsx (existing shadcn component pattern — replicate for new ones)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Standard Stack (versions: react-virtuoso 4.18.6, react-hotkeys-hook 5.2.4)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-27 (npx typeui.sh pull paper), D-02-28 (primary #111111, secondary #8B5CF6)
  </read_first>
  <action>
**Step 1: npm install + shadcn components**

Run these commands from the repository root:

```bash
cd frontend
npm install react-virtuoso@4.18.6 react-hotkeys-hook@5.2.4
npx shadcn@latest add textarea input popover command
```

If the `npx shadcn@latest add` command is interactive (prompts for overwrite), answer yes to all.

After installation verify:
1. `react-virtuoso` and `react-hotkeys-hook` appear in `frontend/package.json` dependencies.
2. Files exist:
   - `frontend/src/components/ui/textarea.tsx`
   - `frontend/src/components/ui/input.tsx`
   - `frontend/src/components/ui/popover.tsx`
   - `frontend/src/components/ui/command.tsx`

Do NOT install `@monaco-editor/react` — it stays as-is per D-02-15. Do NOT run `npm install react-window` — react-virtuoso replaces it.

**Step 2: Apply paper skill tokens to tailwind.config.ts (D-02-27/28)**

First attempt the typeui.sh CLI:
```bash
cd frontend
npx typeui.sh pull paper 2>&1
```

If `typeui.sh` is not available (exits non-zero or "not found"), proceed with the manual fallback below.

**Manual fallback (always apply regardless of typeui.sh outcome):**

Read `frontend/tailwind.config.ts`. Find the `theme.extend` section (or `theme` if no `extend`). Add the paper color tokens into `theme.extend.colors`:

```typescript
// Inside theme.extend.colors (merge with existing, do NOT replace):
"paper-ink": "#111111",        // D-02-28: primary text/brand color
"paper-accent": "#8B5CF6",     // D-02-28: violet accent (reserved uses — see UI-SPEC)
```

Example final shape in tailwind.config.ts:
```typescript
theme: {
  extend: {
    colors: {
      // ... existing colors stay unchanged ...
      "paper-ink": "#111111",
      "paper-accent": "#8B5CF6",
    },
    // ... other extend keys ...
  },
},
```

These tokens make `text-paper-ink` and `bg-paper-accent` (and their Tailwind variants) available for Phase 2 components. The values are locked per D-02-28; do not adjust.
  </action>
  <verify>
    <automated>grep -q "react-virtuoso" /home/thu/dev/projects/ai-translation/frontend/package.json && grep -q "react-hotkeys-hook" /home/thu/dev/projects/ai-translation/frontend/package.json && test -f /home/thu/dev/projects/ai-translation/frontend/src/components/ui/textarea.tsx && grep -q '"paper-ink"' /home/thu/dev/projects/ai-translation/frontend/tailwind.config.ts && grep -q '"paper-accent"' /home/thu/dev/projects/ai-translation/frontend/tailwind.config.ts && echo "PASS"</automated>
  </verify>
  <done>
    - `react-virtuoso` and `react-hotkeys-hook` present in frontend/package.json dependencies
    - All 4 shadcn components exist in frontend/src/components/ui/
    - `frontend/tailwind.config.ts` contains `"paper-ink": "#111111"` and `"paper-accent": "#8B5CF6"` under theme.extend.colors
    - `npm --prefix frontend run build` does not error on missing modules (run after other tasks)
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend conftest.py with Phase 2 fixtures</name>
  <files>
    backend/tests/conftest.py
  </files>
  <read_first>
    - backend/tests/conftest.py (existing: test_engine, db_session, mock_redis, mock_llm_client, mock_arq_ctx)
    - backend/src/app/db/models.py (Job + Segment models — Glossary/GlossaryTerm/SegmentFlag will be added by Plan 02; fixtures reference them by import, not inline)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-01..D-02-09 (schema shapes)
  </read_first>
  <action>
Append to `backend/tests/conftest.py` (after existing fixtures, no changes to existing fixtures):

```python
# ---------------------------------------------------------------------------
# Phase 2: Factory fixtures for Glossary, GlossaryTerm, SegmentFlag
# ---------------------------------------------------------------------------
# NOTE: These fixtures will only be usable after Plan 02 adds Glossary,
# GlossaryTerm, SegmentFlag to backend/src/app/db/models.py. The stub
# test files (created in Task 3 of this plan) will skip/xfail until then.
# ---------------------------------------------------------------------------

@pytest.fixture
def make_glossary(db_session):
    """Factory: create a Glossary row in the test DB.

    IMPORTANT: Uses commit() (not flush()) so rows are visible to the HTTP
    test client which runs in a separate session. flush() only makes rows
    visible within the same session; API-level tests need committed rows.
    """
    import uuid
    from app.db.models import Glossary

    async def _make(
        name: str = "Test Glossary",
        source_lang: str = "vi",
        target_lang: str = "en",
    ) -> "Glossary":
        g = Glossary(
            id=str(uuid.uuid4()),
            name=name,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        db_session.add(g)
        await db_session.commit()
        await db_session.refresh(g)
        return g

    return _make


@pytest.fixture
def make_glossary_term(db_session):
    """Factory: create a GlossaryTerm row in the test DB.

    IMPORTANT: Uses commit() (not flush()) — same reason as make_glossary.
    API-level tests use a separate session and cannot see uncommitted rows.
    """
    import uuid
    from app.db.models import GlossaryTerm

    async def _make(
        glossary_id: str,
        source_term: str = "AICore",
        target_term: str = "AICore",
        notes: str | None = None,
    ) -> "GlossaryTerm":
        t = GlossaryTerm(
            id=str(uuid.uuid4()),
            glossary_id=glossary_id,
            source_term=source_term,
            target_term=target_term,
            notes=notes,
        )
        db_session.add(t)
        await db_session.commit()
        await db_session.refresh(t)
        return t

    return _make


@pytest.fixture
def make_segment_flag(db_session):
    """Factory: create a SegmentFlag row in the test DB."""
    import uuid
    from app.db.models import SegmentFlag, FlagType, FlagSeverity

    async def _make(
        segment_id: str,
        flag_type: str = "overflow",
        severity: str = "warn",
        details: dict | None = None,
    ) -> "SegmentFlag":
        f = SegmentFlag(
            id=str(uuid.uuid4()),
            segment_id=segment_id,
            flag_type=FlagType(flag_type),
            severity=FlagSeverity(severity),
            details=details or {},
        )
        db_session.add(f)
        await db_session.flush()
        return f

    return _make
```

Important: These fixtures use late imports (`from app.db.models import ...`) inside the factory function, so conftest.py can be loaded without error before Plan 02 adds the models. The test files that use them will only run successfully after Plan 02 executes.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/conftest.py --collect-only -q 2>&1; echo "exit:$?"</automated>
  </verify>
  <done>
    - conftest.py loads without ImportError (pytest --collect-only exits 0)
    - Three new fixtures visible: make_glossary, make_glossary_term, make_segment_flag
    - make_glossary and make_glossary_term use commit() + refresh() — not flush()
    - Existing fixtures (test_engine, db_session, mock_redis, mock_llm_client, mock_arq_ctx) unchanged
  </done>
</task>

<task type="auto">
  <name>Task 3: Create backend test stub files (Wave 0 gap coverage)</name>
  <files>
    backend/tests/api/test_glossaries.py
    backend/tests/api/test_segments.py
    backend/tests/services/test_glossary_service.py
    backend/tests/services/test_csv_import.py
    backend/tests/services/test_tbx_import.py
    backend/tests/services/test_post_check.py
    backend/tests/services/test_export_service.py
    backend/tests/workers/test_worker_glossary.py
  </files>
  <read_first>
    - backend/tests/services/test_job_service.py (existing service test pattern — copy structure)
    - backend/tests/api/test_jobs.py (existing API test pattern — copy structure)
    - backend/tests/workers/test_translate_worker.py (existing worker test pattern)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Validation Architecture (exact test names and behaviors)
  </read_first>
  <action>
Create each file as a stub with `pytest.mark.xfail` markers until the implementations land in later plans. Use the exact test function names from VALIDATION.md so the verification map matches.

**`backend/tests/api/test_glossaries.py`** (covers GLOS-01, GLOS-05):
```python
"""Glossary CRUD API tests — GLOS-01, GLOS-05.

Stubs: will pass after Plan 03 implements glossaries.py route.
Response shape: {"glossaries": [...]} — wrapped, mirrors Phase 1 /jobs response.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_list_glossaries_empty(client):
    """GET /glossaries returns {"glossaries": []} when no glossaries exist."""
    resp = await client.get("/glossaries")
    assert resp.status_code == 200
    assert resp.json()["glossaries"] == []


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_create_glossary(client):
    """POST /glossaries creates a glossary row."""
    resp = await client.post(
        "/glossaries",
        json={"name": "AICore VN→EN", "source_lang": "vi", "target_lang": "en"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "AICore VN→EN"
    assert data["source_lang"] == "vi"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_get_glossary_not_found(client):
    """GET /glossaries/{id} returns 404 for unknown id."""
    resp = await client.get("/glossaries/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_delete_glossary(client, make_glossary):
    """DELETE /glossaries/{id} removes glossary and all terms."""
    g = await make_glossary()
    resp = await client.delete(f"/glossaries/{g.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_list_glossaries_filtered_by_pair(client, make_glossary):
    """GET /glossaries?source_lang=vi&target_lang=en returns only matching-pair glossaries."""
    await make_glossary(source_lang="vi", target_lang="en")
    await make_glossary(source_lang="vi", target_lang="ja")
    resp = await client.get("/glossaries?source_lang=vi&target_lang=en")
    assert resp.status_code == 200
    glossaries = resp.json()["glossaries"]
    assert len(glossaries) == 1
    assert glossaries[0]["target_lang"] == "en"
```

**`backend/tests/api/test_segments.py`** (covers REV-02, REV-04):
```python
"""Segment PATCH + regenerate API tests — REV-02, REV-04.

Stubs: will pass after Plan 04 implements segments.py route.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 segments route implementation", strict=False)
async def test_patch_segment_edited_text(client):
    """PATCH /segments/{id} persists edited_text."""
    resp = await client.patch("/segments/test-seg-id", json={"edited_text": "Edited text"})
    assert resp.status_code == 200
    assert resp.json()["edited_text"] == "Edited text"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 segments route implementation", strict=False)
async def test_patch_segment_clear_edit(client):
    """PATCH /segments/{id} with edited_text=null clears the edit."""
    resp = await client.patch("/segments/test-seg-id", json={"edited_text": None})
    assert resp.status_code == 200
    assert resp.json()["edited_text"] is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 segments route implementation", strict=False)
async def test_regenerate(client):
    """POST /segments/{id}/regenerate overwrites translated_text, preserves edited_text — D-02-20."""
    # REV-04: regenerate must not touch edited_text
    resp = await client.post("/segments/test-seg-id/regenerate")
    assert resp.status_code == 200
    data = resp.json()
    assert "translated_text" in data
```

**`backend/tests/services/test_glossary_service.py`** (covers GLOS-01 service layer + update_term):
```python
"""Glossary service CRUD tests — GLOS-01 service layer.

Stubs: will pass after Plan 03 implements glossary_service.py.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossary_service implementation", strict=False)
async def test_create_and_get_glossary(db_session):
    """create_glossary + get_glossary round-trip."""
    from app.services.glossary_service import create_glossary, get_glossary
    g = await create_glossary(db_session, name="Test", source_lang="vi", target_lang="en")
    assert g.id is not None
    fetched = await get_glossary(db_session, g.id)
    assert fetched is not None
    assert fetched.name == "Test"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossary_service implementation", strict=False)
async def test_delete_glossary(db_session, make_glossary):
    """delete_glossary removes the row."""
    from app.services.glossary_service import get_glossary, delete_glossary
    g = await make_glossary()
    await delete_glossary(db_session, g.id)
    assert await get_glossary(db_session, g.id) is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossary_service implementation", strict=False)
async def test_load_glossary_terms_for_job_none(db_session):
    """load_glossary_terms_for_job returns None when glossary_id is None."""
    from app.services.glossary_service import load_glossary_terms_for_job
    result = await load_glossary_terms_for_job(db_session, glossary_id=None)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 update_term implementation", strict=False)
async def test_update_term(db_session, make_glossary, make_glossary_term):
    """update_term patches target_term in place; returns updated GlossaryTerm."""
    from app.services.glossary_service import update_term
    g = await make_glossary()
    t = await make_glossary_term(g.id, source_term="AICore", target_term="AICore")
    updated = await update_term(db_session, t.id, target_term="AICore Inc.")
    assert updated is not None
    assert updated.target_term == "AICore Inc."


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 update_term implementation", strict=False)
async def test_update_term_not_found_returns_none(db_session):
    """update_term returns None for unknown term_id (not 404 at service layer)."""
    from app.services.glossary_service import update_term
    result = await update_term(db_session, "nonexistent-id", target_term="anything")
    assert result is None
```

**`backend/tests/services/test_csv_import.py`** (covers GLOS-02 CSV):
```python
"""CSV glossary import tests — GLOS-02.

Stubs: will pass after Plan 03 implements parse_csv_glossary in glossary_service.py.
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_standard_headers():
    """CSV with source_term,target_term headers parses correctly."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"source_term,target_term,notes\nAICore,AICore,brand name\n"
    terms = parse_csv_glossary(content)
    assert len(terms) == 1
    assert terms[0]["source_term"] == "AICore"
    assert terms[0]["target_term"] == "AICore"
    assert terms[0]["notes"] == "brand name"


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_with_bom():
    """CSV with UTF-8 BOM (Excel export) strips BOM and parses correctly — Pitfall 6."""
    from app.services.glossary_service import parse_csv_glossary
    bom = b"\xef\xbb\xbf"
    content = bom + b"source_term,target_term\nxin ch\xc3\xa0o,hello\n"
    terms = parse_csv_glossary(content)
    assert len(terms) == 1
    assert terms[0]["source_term"] == "xin chào"


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_header_variants():
    """CSV with 'source','target' header aliases are accepted."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"source,target\nterm,translation\n"
    terms = parse_csv_glossary(content)
    assert len(terms) == 1


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_short_term_rejected():
    """Terms shorter than 2 chars are rejected per D-02-07."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"source_term,target_term\nA,B\n"
    with pytest.raises(ValueError, match="at least 2 characters"):
        parse_csv_glossary(content)


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_missing_headers_raises():
    """CSV without required headers raises ValueError."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"col1,col2\nfoo,bar\n"
    with pytest.raises(ValueError):
        parse_csv_glossary(content)
```

**`backend/tests/services/test_tbx_import.py`** (covers GLOS-02 TBX):
```python
"""TBX minimal import tests — GLOS-02."""
from __future__ import annotations

import pytest

_SAMPLE_TBX = b"""<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX-Basic">
  <body>
    <termEntry>
      <langSet xml:lang="vi"><tig><term>xin chào</term></tig></langSet>
      <langSet xml:lang="en"><tig><term>hello</term></tig></langSet>
    </termEntry>
  </body>
</martif>
"""


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service TBX parser", strict=False)
def test_parse_tbx_minimal_valid():
    """Valid TBX-Core file extracts term pairs correctly."""
    from app.services.glossary_service import parse_tbx_minimal
    terms = parse_tbx_minimal(_SAMPLE_TBX, source_lang="vi", target_lang="en")
    assert len(terms) == 1
    assert terms[0]["source_term"] == "xin chào"
    assert terms[0]["target_term"] == "hello"


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service TBX parser", strict=False)
def test_parse_tbx_no_matching_lang_returns_empty():
    """TBX with no entries for the specified pair returns empty list (not error)."""
    from app.services.glossary_service import parse_tbx_minimal
    terms = parse_tbx_minimal(_SAMPLE_TBX, source_lang="zh", target_lang="en")
    assert terms == []
```

**`backend/tests/services/test_post_check.py`** (covers GLOS-04, LAYOUT-01):
```python
"""Post-translation check tests — GLOS-04, LAYOUT-01.

Stubs: will pass after Plan 03 implements run_post_check in glossary_service.py.
Note: run_post_check is in glossary_service.py (not translate_worker.py).

IMPORTANT: test_expansion_ratio_overflow_flag uses a real Segment DB row (not just
FakeSeg) so that run_post_check can write expansion_ratio back to the DB and the
test can assert the SegmentFlag was persisted via a DB query.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_glossary_violation_flag_written(db_session, make_glossary, make_glossary_term):
    """run_post_check writes glossary_violation flag when term absent from output — GLOS-04."""
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag, FlagType
    from sqlalchemy import select

    g = await make_glossary()
    await make_glossary_term(g.id, source_term="AICore", target_term="AICore")
    glossary = {"AICore": "AICore"}

    class FakeSeg:
        id = "seg001"
        source_text = "xin chào từ AICore"

    translated_map = {"seg001": "hello from SomeOtherCompany"}
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=glossary,
        source_lang="vi",
        target_lang="en",
        expansion_thresholds={"vi->en": 0.9},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg001")
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.glossary_violation for f in flags)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_short_term_skipped(db_session):
    """run_post_check skips terms shorter than 2 chars — D-02-07."""
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag
    from sqlalchemy import select

    class FakeSeg:
        id = "seg002"
        source_text = "A single letter"

    glossary = {"A": "B"}  # Both less than 2 chars — must be skipped
    translated_map = {"seg002": "No B in output"}
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=glossary,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg002")
    )
    flags = result.scalars().all()
    assert len(flags) == 0


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_expansion_ratio_overflow_flag(db_session):
    """run_post_check emits overflow flag when ratio exceeds threshold — LAYOUT-01.

    Uses a real Segment DB row (not just FakeSeg) so that:
    - run_post_check can write expansion_ratio via UPDATE Segment WHERE id = seg.id
    - The SegmentFlag INSERT has a valid FK to segments.id (no FK violation)
    - We can assert the flag was persisted via a real DB query
    """
    import uuid
    from app.db.models import Segment, SegmentFlag, FlagType
    from app.services.glossary_service import run_post_check
    from sqlalchemy import select

    # Insert a real Segment row — run_post_check writes expansion_ratio back to it
    seg_id = str(uuid.uuid4())
    seg = Segment(
        id=seg_id,
        job_id="fake-job-id",  # FK not enforced in SQLite test DB
        seq_in_job=0,
        source_text="ab",  # 2 chars
        translated_text="abcdefghij",  # 10 chars → ratio=5.0 > threshold 1.3
    )
    db_session.add(seg)
    await db_session.flush()

    translated_map = {seg_id: "abcdefghij"}
    await run_post_check(
        session=db_session,
        batch_segs=[seg],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={"en->vi": 1.3},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == seg_id)
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.overflow for f in flags)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_placeholder_mismatch_flag_written(db_session):
    """run_post_check writes placeholder_mismatch flag when token missing from output — WARNING 2 fix."""
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag, FlagType
    from sqlalchemy import select

    class FakeSeg:
        id = "seg004"
        source_text = "Visit ⟦T1⟧ for details"  # T1 placeholder from Phase 1 CORE-05

    translated_map = {"seg004": "Truy cập để biết chi tiết"}  # ⟦T1⟧ missing
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg004")
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.placeholder_mismatch for f in flags)


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 run_post_check implementation", strict=False)
async def test_llm_refusal_flag_written(db_session):
    """run_post_check writes llm_refusal flag when output identical to source — heuristic: len > 8 AND identical.

    The heuristic requires len(source_stripped) > 8 to avoid false positives on short
    acronyms (e.g. 'AI' → 'AI' is correct, not a refusal). 'Hello world' is 11 chars
    and passes unchanged, so the flag should fire.
    """
    from app.services.glossary_service import run_post_check
    from app.db.models import SegmentFlag, FlagType
    from sqlalchemy import select

    class FakeSeg:
        id = "seg005"
        source_text = "Hello world"  # 11 chars > 8 threshold

    # LLM returned the source unchanged (refusal heuristic: len > 8 AND identical)
    translated_map = {"seg005": "Hello world"}
    await run_post_check(
        session=db_session,
        batch_segs=[FakeSeg()],
        translated_map=translated_map,
        glossary=None,
        source_lang="en",
        target_lang="vi",
        expansion_thresholds={},
    )
    result = await db_session.execute(
        select(SegmentFlag).where(SegmentFlag.segment_id == "seg005")
    )
    flags = result.scalars().all()
    assert any(f.flag_type == FlagType.llm_refusal for f in flags)
```

**`backend/tests/services/test_export_service.py`** (covers REV-05, REV-06):
```python
"""Export service tests — REV-05, REV-06.

Stubs: will pass after Plan 04 implements export_service.py.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 export_service implementation", strict=False)
async def test_export_prefers_edited_text(db_session, tmp_path):
    """export_job uses edited_text over translated_text when both present — D-02-20."""
    from app.services.export_service import export_job
    # Implementation to be verified once export_service is built


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 export_service implementation", strict=False)
async def test_export_empty_string_edit_not_dropped(db_session, tmp_path):
    """export_job respects edited_text='' (explicit clear) — Pitfall 5: no `or` fallback."""
    from app.services.export_service import export_job
    # edited_text="" must produce "" in output, not fall back to translated_text


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 export_service implementation", strict=False)
async def test_export_idempotent(db_session, tmp_path):
    """Calling export_job twice produces identical output, segment rows unchanged — REV-06."""
    from app.services.export_service import export_job
    # Two exports should produce same file; segment.edited_text unchanged after export
```

**`backend/tests/workers/test_worker_glossary.py`** (covers GLOS-03):
```python
"""Worker glossary injection tests — GLOS-03.

Stubs: will pass after Plan 04 wires glossary into translate_worker.py.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 worker extension", strict=False)
async def test_worker_loads_glossary_terms(mock_arq_ctx, db_session, make_glossary, make_glossary_term):
    """Worker calls translate_batch with glossary dict when job has glossary_id — GLOS-03."""
    g = await make_glossary()
    await make_glossary_term(g.id, source_term="AICore", target_term="AICore")
    # Verify translate_batch called with non-None glossary kwarg


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 worker extension", strict=False)
async def test_worker_passes_none_glossary_when_no_glossary(mock_arq_ctx, db_session):
    """Worker passes glossary=None when job has no glossary_id — GLOS-03."""
    # Verify translate_batch called with glossary=None
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/api/test_glossaries.py backend/tests/api/test_segments.py backend/tests/services/test_glossary_service.py backend/tests/services/test_csv_import.py backend/tests/services/test_tbx_import.py backend/tests/services/test_post_check.py backend/tests/services/test_export_service.py backend/tests/workers/test_worker_glossary.py --collect-only -q 2>&1 | tail -5</automated>
  </verify>
  <done>
    - All 8 backend test files collected by pytest (no syntax errors)
    - All tests marked xfail (not error) — they will pass after feature implementations land
    - test_post_check.py has 5 stubs: violation, short-term-skip, expansion-ratio (real Segment DB row), placeholder_mismatch, llm_refusal (with len > 8 AND identical heuristic documented)
    - test_glossary_service.py has 4 stubs including test_update_term and test_update_term_not_found_returns_none
    - Existing tests unchanged: `uv run pytest backend/tests/ -m "not integration" -x -q` still green
  </done>
</task>

<task type="auto">
  <name>Task 4: Create frontend test stub files</name>
  <files>
    frontend/src/__tests__/SegmentTable.test.tsx
    frontend/src/__tests__/useSegments.test.ts
    frontend/src/__tests__/FlagBadge.test.tsx
    frontend/src/__tests__/GlossarySelect.test.tsx
  </files>
  <read_first>
    - frontend/src/lib/types.ts (existing types — Segment, SegmentFlag will be added in Plan 05)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 1 TanStack v5 pattern (test hook setup)
    - .planning/phases/02-review-ux-glossary/02-UI-SPEC.md §Component Inventory (FlagBadge, SegmentTable props)
  </read_first>
  <action>
Create a `frontend/src/__tests__/` directory if it doesn't exist. Create each test stub using vitest + Testing Library patterns. Use `vi.fn()` for mocks and `describe`/`it` structure.

**`frontend/src/__tests__/FlagBadge.test.tsx`** (covers REV-03):
```tsx
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
// NOTE: FlagBadge will be created in Plan 05
// import { FlagBadge } from "@/components/FlagBadge"

describe("FlagBadge", () => {
  it.todo("renders overflow badge with amber color class")
  it.todo("renders glossary_violation badge with violet color class")
  it.todo("renders placeholder_mismatch badge with orange color class")
  it.todo("renders llm_refusal badge with red color class")
  it.todo("renders correct label text for each flag type")
})
```

**`frontend/src/__tests__/SegmentTable.test.tsx`** (covers REV-01):
```tsx
import { describe, it, expect } from "vitest"
// NOTE: SegmentTable will be created in Plan 06
// import { SegmentTable } from "@/components/SegmentTable"

describe("SegmentTable", () => {
  it.todo("renders all segments without DOM explosion — REV-01")
  it.todo("focused segment row has ring-violet-200 class")
  it.todo("j key advances focused index")
  it.todo("k key decrements focused index")
  it.todo("n key jumps to next flagged segment")
  it.todo("e key focuses the target textarea of focused row")
})
```

**`frontend/src/__tests__/useSegments.test.ts`** (covers REV-02 optimistic update + rollback):
```typescript
import { describe, it, expect, vi } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
// NOTE: useSegments/useSegmentPatch will be created in Plan 06
// import { useSegmentPatch } from "@/hooks/useSegments"

describe("useSegmentPatch", () => {
  it.todo("optimistic update sets edited_text in cache immediately — D-02-19")
  it.todo("cache rollback restores previous value on PATCH error — D-02-19")
  it.todo("toast 'Could not save — edit restored.' shown on error — D-02-18")
  it.todo("cancelQueries called in onMutate before setQueryData — Pitfall 4")
})
```

**`frontend/src/__tests__/GlossarySelect.test.tsx`** (covers UPLD-04):
```tsx
import { describe, it, expect } from "vitest"
// NOTE: GlossarySelect will be created in Plan 05
// import { GlossarySelect } from "@/components/GlossarySelect"

describe("GlossarySelect", () => {
  it.todo("hidden when source_lang or target_lang not yet selected — D-02-25")
  it.todo("shows 'No glossary for this pair' when API returns empty list for pair — D-02-25")
  it.todo("shows glossary options when matching-pair glossaries exist")
  it.todo("non-matching-pair glossaries are hidden (not greyed-out) — D-02-25")
  it.todo("selected glossary_id passed to onChange handler")
})
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && npm --prefix frontend run test -- --reporter=verbose 2>&1 | grep -E "todo|pass|fail|collect" | head -20</automated>
  </verify>
  <done>
    - 4 frontend test files created in frontend/src/__tests__/
    - vitest can discover and collect all tests (all marked .todo — zero failures)
    - `npm --prefix frontend run test` exits 0 (todo tests do not cause failure)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Dev tool → local filesystem | npm install + shadcn CLI write files; only affects local dev environment |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01-01 | Tampering | npm install (supply chain) | accept | react-virtuoso and react-hotkeys-hook are vetted packages (>1M weekly downloads, published by known maintainers). Standard npm audit applies. |
| T-02-01-02 | Tampering | shadcn@latest CLI | accept | shadcn is official shadcn/ui CLI (ui.shadcn.com). Only installs to local src/ — no production surface at this stage. |
</threat_model>

<verification>
After all tasks in this plan:

1. `grep -q "react-virtuoso" frontend/package.json` — exits 0
2. `grep -q "react-hotkeys-hook" frontend/package.json` — exits 0
3. All 4 shadcn components exist: `ls frontend/src/components/ui/{textarea,input,popover,command}.tsx`
4. `grep -q '"paper-ink"' frontend/tailwind.config.ts && grep -q '"paper-accent"' frontend/tailwind.config.ts` — exits 0
5. `uv run --directory backend pytest backend/tests/api/test_glossaries.py --collect-only -q` — collects 5 tests, no errors
6. `uv run --directory backend pytest backend/tests/ -m "not integration" -x -q` — existing tests still green
7. `npm --prefix frontend run test -- --reporter=dot` — exits 0
</verification>

<success_criteria>
- react-virtuoso@4.18.6 and react-hotkeys-hook@5.2.4 in frontend/package.json
- 4 shadcn components added to frontend/src/components/ui/
- frontend/tailwind.config.ts has paper-ink (#111111) and paper-accent (#8B5CF6) under theme.extend.colors
- 8 backend test stubs collected by pytest (all xfail); test_post_check.py has 5 stubs (including placeholder_mismatch + llm_refusal with len > 8 AND identical heuristic)
- test_glossary_service.py has 4 stubs including test_update_term and test_update_term_not_found_returns_none
- test_expansion_ratio_overflow_flag uses a real Segment DB row (not FakeSeg) so expansion_ratio write and FK constraint work correctly
- 4 frontend test stubs collected by vitest (all todo)
- conftest.py has make_glossary, make_glossary_term (both using commit()+refresh()), make_segment_flag fixtures
- All existing 131+ unit tests still pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-01-SUMMARY.md`
</output>
