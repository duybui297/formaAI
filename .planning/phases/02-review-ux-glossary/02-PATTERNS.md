# Phase 2: Review UX + Glossary — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 27 new/modified files (13 backend + 14 frontend)
**Analogs found:** 27 / 27 — all files have codebase analogs from Phase 1

---

## File Classification

### Backend (Python / FastAPI)

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `backend/src/app/db/models.py` (extend) | model | CRUD | self (Phase 1 `Job`, `Segment`) | exact |
| `backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py` | migration | — | `e0e8f781ec72_init.py` | exact |
| `backend/src/app/api/routes/glossaries.py` (replace stub) | controller | CRUD | `backend/src/app/api/routes/jobs.py` | role-match |
| `backend/src/app/api/routes/segments.py` (new) | controller | request-response | `backend/src/app/api/routes/jobs.py` | role-match |
| `backend/src/app/api/routes/export.py` (new) | controller | file-I/O | `backend/src/app/api/routes/jobs.py` lines 90-128 | role-match |
| `backend/src/app/services/glossary_service.py` (new) | service | CRUD | `backend/src/app/services/job_service.py` | exact |
| `backend/src/app/services/export_service.py` (new) | service | file-I/O | `backend/src/app/services/job_service.py` + `reassembler.py` | role-match |
| `backend/src/app/api/routes/upload.py` (extend) | controller | request-response | self | exact |
| `backend/src/app/workers/translate_worker.py` (extend) | worker | event-driven | self (Phase 1 worker) | exact |
| `backend/src/app/pipeline/docx/reassembler.py` (extend) | service | file-I/O | self | exact |
| `backend/src/app/services/job_service.py` (extend) | service | CRUD | self | exact |
| `backend/src/app/core/config.py` (extend) | config | — | self | exact |

### Frontend (Next.js 16 App Router)

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `frontend/src/app/layout.tsx` (extend) | component | — | self | exact |
| `frontend/src/lib/types.ts` (extend) | utility | — | self | exact |
| `frontend/src/app/jobs/[id]/page.tsx` (extend) | component | request-response | self | exact |
| `frontend/src/app/jobs/[id]/review/page.tsx` (new) | component | request-response | `frontend/src/app/jobs/[id]/page.tsx` | role-match |
| `frontend/src/app/glossaries/page.tsx` (new) | component | request-response | `frontend/src/app/jobs/page.tsx` | role-match |
| `frontend/src/app/glossaries/[id]/page.tsx` (new) | component | request-response | `frontend/src/app/jobs/[id]/page.tsx` | role-match |
| `frontend/src/hooks/useSegments.ts` (new) | hook | request-response | `frontend/src/hooks/useJobProgress.ts` | role-match |
| `frontend/src/components/UploadForm.tsx` (extend) | component | request-response | self | exact |
| `frontend/src/components/GlossarySelect.tsx` (new) | component | request-response | `frontend/src/components/LanguageSelect.tsx` | exact |
| `frontend/src/components/FlagBadge.tsx` (new) | component | — | `frontend/src/components/StatusBadge.tsx` | exact |
| `frontend/src/components/NavBar.tsx` (extend) | component | — | self | exact |
| `frontend/src/components/SegmentTable.tsx` (new) | component | request-response | `frontend/src/components/JobsTable.tsx` | role-match |
| `frontend/src/components/SegmentRow.tsx` (new) | component | request-response | `frontend/src/components/JobsTable.tsx` lines 40-110 | role-match |
| `frontend/src/components/ReviewFilterBar.tsx` (new) | component | — | `frontend/src/components/StageIndicator.tsx` | partial |
| `frontend/src/components/ReviewPageHeader.tsx` (new) | component | — | `frontend/src/components/JobMetaRow.tsx` | role-match |
| `frontend/src/components/KeyboardHelpPanel.tsx` (new) | component | — | `frontend/src/components/TrackedChangesModal.tsx` | partial |
| `frontend/src/components/glossary/GlossaryList.tsx` (new) | component | request-response | `frontend/src/components/JobsTable.tsx` | exact |
| `frontend/src/components/glossary/GlossaryCreateDialog.tsx` (new) | component | request-response | `frontend/src/components/TrackedChangesModal.tsx` | exact |
| `frontend/src/components/glossary/TermsTable.tsx` (new) | component | CRUD | `frontend/src/components/JobsTable.tsx` | role-match |
| `frontend/src/components/glossary/CSVUploadButton.tsx` (new) | component | file-I/O | `frontend/src/components/UploadForm.tsx` | partial |

---

## Pattern Assignments

### `backend/src/app/db/models.py` (extend — model, CRUD)

**Analog:** self (existing `Job` and `Segment` classes, lines 1-123)

**Existing model pattern to replicate** (`models.py` lines 37-122):
```python
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, Float, JSON, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Enum pattern: use Python enum + SAEnum; str-mixin for JSON serialization
class FlagType(str, enum.Enum):
    overflow = "overflow"
    glossary_violation = "glossary_violation"
    placeholder_mismatch = "placeholder_mismatch"
    llm_refusal = "llm_refusal"

class FlagSeverity(str, enum.Enum):
    info = "info"
    warn = "warn"
    block = "block"

# Model pattern: String(36) PK for UUID (SQLite compat), lambda default
class Glossary(Base):
    __tablename__ = "glossaries"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # ... columns ...
    terms: Mapped[list["GlossaryTerm"]] = relationship(
        "GlossaryTerm", back_populates="glossary", lazy="selectin"
    )
```

**Deviation from Phase 1:** Three new tables (`glossaries`, `glossary_terms`, `segment_flags`). Existing `Job` gets `glossary_id` FK column. Existing `Segment` gets `edited_text TEXT NULL` and `expansion_ratio FLOAT NULL`. All new enums use `native_enum=False` is set at migration level — models use normal SAEnum. `segment_flags` uses `JSON` column type (not PostgreSQL JSONB — SQLite compat).

**Existing `Job` extend pattern** (`models.py` lines 37-89):
```python
# Add after existing tracked_changes_action column:
glossary_id: Mapped[str | None] = mapped_column(
    String(36),
    ForeignKey("glossaries.id", ondelete="SET NULL"),
    nullable=True,
)
```

**Existing `Segment` extend pattern** (`models.py` lines 92-122):
```python
# Add after translated_text column:
edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
expansion_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
```

---

### `backend/src/app/db/migrations/versions/0002_phase2_glossary_flags.py` (migration)

**Analog:** `backend/src/app/db/migrations/versions/e0e8f781ec72_init.py`

**Migration file header pattern** (lines 1-18):
```python
"""phase2 glossary flags

Revision ID: <auto-generated>
Revises: e0e8f781ec72
Create Date: <auto-generated>
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '<auto-generated>'
down_revision: Union[str, None] = 'e0e8f781ec72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Core migration pattern** — `op.create_table` block from `e0e8f781ec72_init.py` lines 22-57 is the exact template. Key differences for Phase 2:

- Use `sa.Enum(..., native_enum=False)` for `flag_type` and `severity` columns — avoids PostgreSQL named TYPE creation, maintains SQLite compat in tests.
- `op.create_unique_constraint` for `(glossary_id, source_term)` after table create.
- `op.add_column` + `op.create_foreign_key` pattern for `jobs.glossary_id` and `segments.edited_text` / `segments.expansion_ratio`.
- `downgrade()` must drop FK constraints before dropping columns (see Phase 1 `downgrade()` lines 61-66 for sequence pattern).

**Full migration pattern from RESEARCH.md Section 6** is the authoritative reference — implement exactly as specified there.

---

### `backend/src/app/api/routes/glossaries.py` (replace stub — controller, CRUD)

**Analog:** `backend/src/app/api/routes/jobs.py` (lines 1-128)

**Imports pattern** (`jobs.py` lines 1-24):
```python
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Glossary, GlossaryTerm
from app.db.session import get_session
from app.services.glossary_service import (
    create_glossary, get_glossary, list_glossaries,
    update_glossary, delete_glossary, create_term, delete_term,
    import_csv_terms,
)

log = structlog.get_logger()
router = APIRouter()
```

**List endpoint pattern** (`jobs.py` lines 55-67):
```python
@router.get("/glossaries")
async def list_glossaries_endpoint(
    source_lang: str | None = None,
    target_lang: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-01/05: List glossaries, optionally filtered by language pair (UPLD-04 picker)."""
    glossaries = await list_glossaries(session, source_lang=source_lang, target_lang=target_lang)
    return {"glossaries": [_glossary_to_dict(g) for g in glossaries]}
```

**Get-with-404 pattern** (`jobs.py` lines 70-87):
```python
@router.get("/glossaries/{glossary_id}")
async def get_glossary_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    g = await get_glossary(session, glossary_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    return _glossary_to_dict(g)
```

**FileResponse pattern for CSV import** (`jobs.py` lines 90-128 adapted):
```python
@router.post("/glossaries/{glossary_id}/terms/import", status_code=200)
async def import_terms(
    glossary_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-02: CSV/TBX import. Returns {imported: N, skipped_duplicates: M}."""
    g = await get_glossary(session, glossary_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    content = await file.read()
    ext = Path(file.filename or "").suffix.lower()
    try:
        result = await import_csv_terms(session, g, content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return result
```

**Serializer helper pattern** (`jobs.py` lines 31-52):
```python
def _glossary_to_dict(g: Glossary) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "source_lang": g.source_lang,
        "target_lang": g.target_lang,
        "term_count": len(g.terms),
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
```

---

### `backend/src/app/api/routes/segments.py` (new — controller, request-response)

**Analog:** `backend/src/app/api/routes/jobs.py`

**Imports + router setup**: copy `jobs.py` lines 1-24 pattern, swap models/services.

**GET list with flags** (extend `jobs.py` list pattern):
```python
@router.get("/jobs/{job_id}/segments")
async def list_segments(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """REV-01: Return all segments with flags for the review UI."""
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # Load segments with flags (eager load via relationship)
    segments = await get_segments_with_flags(session, job_id)
    return {"segments": [_segment_to_dict(s) for s in segments]}
```

**PATCH endpoint pattern** (new pattern, follows FastAPI Depends + HTTPException convention):
```python
from pydantic import BaseModel, Field

class SegmentPatchRequest(BaseModel, frozen=True):
    edited_text: str | None = Field(default=..., max_length=10_000)

@router.patch("/segments/{segment_id}", status_code=200)
async def patch_segment(
    segment_id: str,
    body: SegmentPatchRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """REV-02: Persist edited_text. edited_text=None clears the edit (reverts to translated_text on export)."""
    seg = await get_segment(session, segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    await update_segment_edited_text(session, segment_id, body.edited_text)
    return {"segment_id": segment_id, "edited_text": body.edited_text}
```

**Regenerate endpoint** (from RESEARCH.md Section 8):
```python
@router.post("/segments/{segment_id}/regenerate", status_code=200)
async def regenerate_segment(
    segment_id: str,
    session: AsyncSession = Depends(get_session),
    llm_client: AsyncOpenAI = Depends(get_llm_client),
) -> dict:
    """REV-04: Sync single-segment re-translate. Overwrites translated_text; edited_text untouched (D-02-20)."""
```

**Note on `get_llm_client` dependency:** Add to `backend/src/app/api/dependencies.py` alongside existing `get_arq_pool` and `get_redis`. Pattern: `return request.app.state.llm_client` (stored in lifespan, same as arq_pool).

---

### `backend/src/app/api/routes/export.py` (new — controller, file-I/O)

**Analog:** `backend/src/app/api/routes/jobs.py` lines 90-128 (download endpoint)

**Core pattern** (`jobs.py` lines 90-128):
```python
from fastapi.responses import FileResponse

@router.post("/jobs/{job_id}/export")
async def export_document(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """REV-05/06: Idempotent export using edited_text ?? translated_text. Advisory lock on job_id."""
    try:
        output_path = await export_service.export_job(session, job_id, settings.data_dir)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(output_path).name,
    )
```

**Deviation:** `POST` (not `GET`) — export is a write operation (reassembles file). Status code 200 + `FileResponse` (same as download endpoint). Guard: `job.status` must be in `{"done", "needs_review"}` — same set as `_DOWNLOADABLE_STATUSES` in `jobs.py` line 28.

---

### `backend/src/app/services/glossary_service.py` (new — service, CRUD)

**Analog:** `backend/src/app/services/job_service.py` (lines 1-162)

**Module header pattern** (`job_service.py` lines 1-14):
```python
"""
Glossary service: CRUD functions for Glossary and GlossaryTerm rows.

D-02-01: glossaries + glossary_terms two-table schema.
D-02-03: (glossary_id, source_term) unique constraint; hard-delete only.
D-02-04: CSV primary, TBX minimal via ElementTree.
"""
from __future__ import annotations
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Glossary, GlossaryTerm
import structlog

log = structlog.get_logger()
```

**CRUD function pattern** (`job_service.py` lines 25-53):
```python
async def create_glossary(
    session: AsyncSession,
    name: str,
    source_lang: str,
    target_lang: str,
) -> Glossary:
    g = Glossary(name=name, source_lang=source_lang, target_lang=target_lang)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return g

async def get_glossary(session: AsyncSession, glossary_id: str) -> Glossary | None:
    result = await session.execute(select(Glossary).where(Glossary.id == glossary_id))
    return result.scalar_one_or_none()
```

**State machine / business logic** (`job_service.py` lines 56-59 pattern for guarded update):
```python
async def update_glossary_name(
    session: AsyncSession,
    glossary_id: str,
    name: str,
) -> Glossary | None:
    g = await get_glossary(session, glossary_id)
    if g is None:
        return None
    g.name = name
    await session.commit()
    return g
```

**CSV/TBX parsers**: implement as module-level functions in `glossary_service.py` using patterns from RESEARCH.md Section 4. `parse_csv_glossary` and `parse_tbx_minimal` both return `list[dict]` with `{source_term, target_term, notes}` shape — same output, uniform downstream handling.

**`load_glossary_terms_for_job` pattern** (RESEARCH.md Section 5):
```python
async def load_glossary_terms_for_job(
    session: AsyncSession, glossary_id: str | None
) -> dict[str, str] | None:
    """Returns {source_term: target_term} dict or None. Called by worker before translate loop."""
    if glossary_id is None:
        return None
    result = await session.execute(
        select(GlossaryTerm.source_term, GlossaryTerm.target_term)
        .where(GlossaryTerm.glossary_id == glossary_id)
    )
    rows = result.all()
    return {row.source_term: row.target_term for row in rows} if rows else None
```

---

### `backend/src/app/services/export_service.py` (new — service, file-I/O)

**Analog:** `backend/src/app/services/job_service.py` structure + `backend/src/app/pipeline/docx/reassembler.py` for the reassembly call

**Advisory lock + idempotent export pattern** (RESEARCH.md Section 7):
```python
import asyncio
from weakref import WeakValueDictionary
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Job, Segment, JobStatus

_export_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
_locks_mutex = asyncio.Lock()

async def get_export_lock(job_id: str) -> asyncio.Lock:
    async with _locks_mutex:
        lock = _export_locks.get(job_id)
        if lock is None:
            lock = asyncio.Lock()
            _export_locks[job_id] = lock
        return lock

async def export_job(session: AsyncSession, job_id: str, data_dir: str) -> str:
    """REV-06: Advisory lock + read-snapshot; never mutates segment rows."""
    lock = await get_export_lock(job_id)
    async with lock:
        # ... load job, validate status, load segments, reassemble ...
        # D-02-20: edited_text if not None else translated_text (explicit None check, not `or`)
        translated_map = {
            seg.id: (seg.edited_text if seg.edited_text is not None else seg.translated_text or "")
            for seg in segments
        }
```

**Deviation from job_service pattern:** Uses `asyncio.Lock` advisory pattern (not DB-only state machine). Returns file path as `str` (caller wraps in `FileResponse`).

---

### `backend/src/app/api/routes/upload.py` (extend — controller, request-response)

**Analog:** self (lines 1-156)

**Extension point** — add `glossary_id` Form field after `tracked_changes_action` (line 46):
```python
# In function signature, after tracked_changes_action:
glossary_id: str | None = Form(None),
```

**Validation pattern** (copy existing target_lang validation at lines 83-88):
```python
# After language validation block, add:
if glossary_id is not None:
    g = await get_glossary(session, glossary_id)
    if g is None:
        raise HTTPException(status_code=422, detail="Glossary not found.")
    if g.source_lang != source_lang or g.target_lang != target_lang:
        raise HTTPException(
            status_code=422,
            detail="The selected glossary does not match the language pair.",
        )
```

**Pass-through to create_job** (extend call at line 125):
```python
job = await create_job(
    ...,
    glossary_id=glossary_id,  # new kwarg
)
```

---

### `backend/src/app/workers/translate_worker.py` (extend — worker, event-driven)

**Analog:** self (lines 1-end)

**Extension points** — three additions inside `_run_translation()`:

1. Before batch loop, load glossary (RESEARCH.md Section 5):
```python
from app.services.glossary_service import load_glossary_terms_for_job
glossary: dict[str, str] | None = await load_glossary_terms_for_job(session, job.glossary_id)
```

2. In `_translate_one_batch()`, replace `glossary=None` with `glossary=glossary`.

3. After `translated_map` is populated for each batch, call post-check (RESEARCH.md Section 5):
```python
from app.services.glossary_service import run_post_check
await run_post_check(
    session=session,
    batch_segs=batch_segs,
    translated_map=translated_map,
    glossary=glossary,
    source_lang=job.source_lang,
    target_lang=job.target_lang,
    expansion_thresholds=ctx["settings"].expansion_thresholds_dict,
)
```

**`run_post_check` lives in `glossary_service.py`** (same file as other glossary helpers) — add it there, not in the worker module. Worker calls it; service owns the logic.

---

### `backend/src/app/pipeline/docx/reassembler.py` (extend — service, file-I/O)

**Analog:** self (lines 1-end)

**Extension point** — the reassembler's `reassemble_docx` and `reassemble_docx_runs` functions receive a `translated_texts: dict[str, str]` parameter. Phase 2's only change is in the caller (`export_service.py`) — the map is built with `edited_text ?? translated_text` before calling the reassembler. The reassembler itself does NOT change; it receives the resolved map and writes it.

**DOCX-02 invariant stays unchanged** — run-merge pattern in `write_translated_paragraph` (lines 28-55) must not be touched.

---

### `backend/src/app/core/config.py` (extend — config)

**Analog:** self (lines 1-46)

**Extension pattern** — add after `worker_concurrency` field (line 32):
```python
# D-02-12: expansion ratio thresholds per language pair (JSON string)
expansion_ratio_thresholds: str = Field(
    default='{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}',
    description="JSON map of 'src->tgt' to float threshold. Tune empirically.",
)

@property
def expansion_thresholds_dict(self) -> dict[str, float]:
    import json
    return json.loads(self.expansion_ratio_thresholds)
```

---

### `frontend/src/lib/types.ts` (extend — utility)

**Analog:** self (lines 1-54)

**Existing union type pattern** (`types.ts` lines 1-2):
```typescript
// Add after JobSummary interface:
export type FlagType = "overflow" | "glossary_violation" | "placeholder_mismatch" | "llm_refusal"
export type FlagSeverity = "info" | "warn" | "block"

export interface SegmentFlag {
  id: string
  segment_id: string
  flag_type: FlagType
  severity: FlagSeverity
  details: Record<string, unknown> | null
  created_at: string
}

export interface Segment {
  id: string
  seq_in_job: number
  source_text: string
  translated_text: string | null
  edited_text: string | null
  expansion_ratio: number | null
  flags: SegmentFlag[]
}

export interface Glossary {
  id: string
  name: string
  source_lang: string
  target_lang: string
  term_count: number
  created_at: string
  updated_at: string
}

export interface GlossaryTerm {
  id: string
  glossary_id: string
  source_term: string
  target_term: string
  notes: string | null
  created_at: string
}
```

---

### `frontend/src/app/layout.tsx` (extend — component)

**Analog:** self (lines 1-32)

**Font extension pattern** (UI-SPEC §Typography — add after existing `inter` declaration, lines 8-11):
```typescript
import { Roboto, Montserrat, PT_Mono } from "next/font/google"

const roboto = Roboto({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-roboto",
  display: "swap",
})
const montserrat = Montserrat({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-montserrat",
  display: "swap",
})
const ptMono = PT_Mono({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-pt-mono",
  display: "swap",
})
```

Apply all four font variables to `<html>`:
```typescript
<html lang="en" className={`${inter.variable} ${roboto.variable} ${montserrat.variable} ${ptMono.variable}`}>
```

**Tailwind config extension** (add to `fontFamily` in `frontend/tailwind.config.ts`):
```typescript
fontFamily: {
  sans: ["var(--font-roboto)", "var(--font-inter)", "system-ui", "sans-serif"],
  heading: ["var(--font-montserrat)", "system-ui", "sans-serif"],
  mono: ["var(--font-pt-mono)", "ui-monospace", "monospace"],
}
```

---

### `frontend/src/hooks/useSegments.ts` (new — hook, request-response)

**Analog:** `frontend/src/hooks/useJobProgress.ts` (lines 1-45) — TanStack Query cache pattern

**Query pattern** (`useJobProgress.ts` lines 34-44):
```typescript
"use client"
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query"
import type { Segment } from "@/lib/types"

export function useSegments(jobId: string) {
  return useQuery<Segment[]>({
    queryKey: ["segments", jobId],
    queryFn: () => fetch(`/api/jobs/${jobId}/segments`).then(r => r.json()).then(d => d.segments),
    staleTime: 0,
  })
}
```

**Optimistic mutation pattern** (from RESEARCH.md Section 1 — exact v5 pattern):
```typescript
export function useSegmentPatch(jobId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ segmentId, editedText }: { segmentId: string; editedText: string | null }) => {
      const res = await fetch(`/api/segments/${segmentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edited_text: editedText }),
      })
      if (!res.ok) throw new Error("Save failed")
      return res.json()
    },
    onMutate: async ({ segmentId, editedText }) => {
      await queryClient.cancelQueries({ queryKey: ["segments", jobId] })
      const previousSegments = queryClient.getQueryData<Segment[]>(["segments", jobId])
      queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
        old?.map((seg) => seg.id === segmentId ? { ...seg, edited_text: editedText } : seg) ?? []
      )
      return { previousSegments }
    },
    onError: (_err, _vars, context) => {
      if (context?.previousSegments) {
        queryClient.setQueryData(["segments", jobId], context.previousSegments)
      }
      toast({ title: "Could not save — edit restored.", variant: "destructive" })
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["segments", jobId] })
    },
  })
}
```

**Critical note:** `cancelQueries` MUST run before `setQueryData` in `onMutate`. v5 pattern — `onMutate` receives `(variables)`, return value becomes `context` in `onError`. Many online examples are v4 — do not copy them.

---

### `frontend/src/components/GlossarySelect.tsx` (new — component, request-response)

**Analog:** `frontend/src/components/LanguageSelect.tsx` (lines 1-83) — exact pattern

**Full pattern from `LanguageSelect.tsx`:**
```typescript
"use client"
import { useQuery } from "@tanstack/react-query"
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select"

interface GlossarySelectProps {
  sourceLang: string
  targetLang: string
  value: string | null           // glossary_id or null
  onValueChange: (id: string | null) => void
  disabled?: boolean
}

export function GlossarySelect({ sourceLang, targetLang, value, onValueChange, disabled }: GlossarySelectProps) {
  const { data } = useQuery<{ glossaries: Glossary[] }>({
    queryKey: ["glossaries", sourceLang, targetLang],
    queryFn: () => fetch(`/api/glossaries?source_lang=${sourceLang}&target_lang=${targetLang}`).then(r => r.json()),
    enabled: !!sourceLang && !!targetLang,
    staleTime: 30_000,
  })
  const glossaries = data?.glossaries ?? []
  // ...
}
```

**Deviation from `LanguageSelect`:** Props take `sourceLang + targetLang` (not `includeAutoDetect`). `queryKey` includes both lang params so cache updates when pair changes. Empty state renders "No glossary for this pair — create one" text link (not empty Select).

---

### `frontend/src/components/FlagBadge.tsx` (new — component)

**Analog:** `frontend/src/components/StatusBadge.tsx` (lines 1-35) — exact pattern

**Pattern from `StatusBadge.tsx`:**
```typescript
// Copy the Record<K, string> style map pattern:
const FLAG_STYLES: Record<FlagType, string> = {
  overflow: "text-amber-600 border-amber-200 bg-amber-50",
  glossary_violation: "text-violet-700 border-violet-200 bg-violet-50",
  placeholder_mismatch: "text-orange-700 border-orange-200 bg-orange-50",
  llm_refusal: "text-red-700 border-red-200 bg-red-50",
}
const FLAG_LABELS: Record<FlagType, string> = {
  overflow: "Overflow",
  glossary_violation: "Glossary violation",
  placeholder_mismatch: "Placeholder",
  llm_refusal: "Refusal",
}

// Same Badge + cn composition as StatusBadge.tsx lines 26-34
```

**Colors from UI-SPEC §Color** (semantic flag colors table) — use those exact Tailwind classes. `variant="outline"` on Badge same as StatusBadge.

---

### `frontend/src/components/NavBar.tsx` (extend — component)

**Analog:** self (lines 29-53)

**Extension point** — add "Glossaries" link after "Jobs" link (line 43):
```typescript
<Link
  href="/glossaries"
  className={`text-sm ${pathname?.startsWith("/glossaries") ? "text-violet-600 font-medium" : "text-slate-600 hover:text-slate-900"}`}
>
  Glossaries
</Link>
```

**Deviation:** Active link color changes from `text-indigo-600` (Phase 1 accent) to `text-violet-600` (Phase 2 paper skill accent). Update existing Upload/Jobs links in the same pass if updating accent.

---

### `frontend/src/components/SegmentTable.tsx` (new — component, request-response)

**Analog:** `frontend/src/components/JobsTable.tsx` (outer Table structure) + react-virtuoso pattern from RESEARCH.md Section 2

**Pattern from RESEARCH.md Section 2 (verbatim):**
```typescript
"use client"
import { Virtuoso, VirtuosoHandle } from "react-virtuoso"
import { useRef, useCallback } from "react"

export function SegmentTable({ segments, focusedIndex, onFocusChange }: SegmentTableProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null)

  const scrollToIndex = useCallback((index: number) => {
    virtuosoRef.current?.scrollIntoView({ index, behavior: "auto" })
    onFocusChange(index)
  }, [onFocusChange])

  return (
    <Virtuoso
      ref={virtuosoRef}
      style={{ height: "calc(100vh - 168px)" }}  // 168px = nav(56) + review header(64) + filter bar(48)
      data={segments}
      increaseViewportBy={{ top: 300, bottom: 500 }}
      itemContent={(index, segment) => (
        <SegmentRow segment={segment} isFocused={index === focusedIndex} onFocus={() => onFocusChange(index)} />
      )}
    />
  )
}
```

**Critical:** Virtuoso MUST have explicit height via `style={{ height: "..." }}`. Without it, collapses to 0px and renders nothing. Use `increaseViewportBy` not `overscan` (v4+ API).

---

### `frontend/src/components/SegmentRow.tsx` (new — component, request-response)

**Analog:** `frontend/src/components/JobsTable.tsx` row structure (lines 52-108) + debounce pattern from RESEARCH.md Section 1

**Row structure pattern** (`JobsTable.tsx` lines 52-75):
```typescript
// Three-cell row: index | source | target | flags
// Copy TableRow hover + border-b pattern from JobsTable.tsx lines 53-58
<div className={`flex items-start border-b border-slate-100 min-h-[48px] ${isFocused ? "ring-1 ring-violet-200" : ""}`}>
  <SegmentIndex seq={segment.seq_in_job} />
  <SourceCell text={segment.source_text} />
  <TargetCell segment={segment} patchMutation={patchMutation} />
  <FlagCell flags={segment.flags} />
</div>
```

**Debounce pattern** (RESEARCH.md Section 1):
```typescript
const debounceRef = useRef<ReturnType<typeof setTimeout>>()

const handleChange = (value: string) => {
  setLocalValue(value)  // instant local state for smooth typing
  clearTimeout(debounceRef.current)
  debounceRef.current = setTimeout(() => {
    patchMutation.mutate({ segmentId: segment.id, editedText: value })
  }, 500)  // D-02-18: 500ms debounce
}

useEffect(() => () => clearTimeout(debounceRef.current), [])
```

**Textarea styling** (UI-SPEC §TargetCell): `min-h-[48px]`, `ring-violet-500` on focus, `bg-white`, `font-sans` (Roboto). Source cell: `font-mono text-xs` (PT Mono).

---

### `frontend/src/app/jobs/[id]/review/page.tsx` (new — component, request-response)

**Analog:** `frontend/src/app/jobs/[id]/page.tsx` (lines 1-166)

**Page skeleton pattern** (`jobs/[id]/page.tsx` lines 18-30):
```typescript
"use client"
import { use } from "react"
// Next.js 16 async params: unwrap with React.use() per D-20
export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: jobId } = use(params)
  // ... TanStack hooks ...
}
```

**Loading skeleton pattern** (`jobs/[id]/page.tsx` lines 34-44): copy Skeleton composition pattern for initial load state.

**NavBar + main + back link pattern** (`jobs/[id]/page.tsx` lines 71-80): copy `<NavBar />` + `<main>` wrapper + `<Link href="/jobs">` back-link pattern. Change `href="/jobs"` and `max-w-3xl` to `max-w-7xl` for review page (UI-SPEC exception).

**Keyboard hook integration** (RESEARCH.md Section 3):
```typescript
import { useHotkeys } from "react-hotkeys-hook"
// ... call useReviewKeyboard({ focusedIndex, ... }) which internally calls useHotkeys
```

---

### `frontend/src/app/glossaries/page.tsx` (new — component, request-response)

**Analog:** `frontend/src/app/jobs/page.tsx`

**Page structure** (`jobs/page.tsx` pattern — list page with TanStack query + table component):
```typescript
"use client"
import { useQuery } from "@tanstack/react-query"
import { NavBar } from "@/components/NavBar"
import { GlossaryList } from "@/components/glossary/GlossaryList"

export default function GlossariesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["glossaries"],
    queryFn: () => fetch("/api/glossaries").then(r => r.json()),
  })
  // Loading → Skeleton; empty → empty state; list → GlossaryList
}
```

**`max-w-4xl` content width** (UI-SPEC exception — glossary pages are `max-w-4xl`, not `max-w-3xl`).

---

### `frontend/src/components/glossary/GlossaryList.tsx` (new — component, request-response)

**Analog:** `frontend/src/components/JobsTable.tsx` (lines 1-110) — exact structural match

**Full Table composition pattern** (`JobsTable.tsx` lines 35-110):
```typescript
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"

// Copy: TableHeader with TableHead columns, TableBody with TableRow map,
// hover:bg-slate-50, onClick row navigation, actions cell with e.stopPropagation()
```

**Column set:** Name | Language Pair | Terms (#) | Created | Actions (Edit, Delete). Actions cell pattern: copy `JobsTable.tsx` lines 77-107 `div.flex.items-center.justify-end.gap-1` with `Button` ghost/sm.

---

### `frontend/src/components/glossary/GlossaryCreateDialog.tsx` (new — component, request-response)

**Analog:** `frontend/src/components/TrackedChangesModal.tsx` (lines 1-108) — Dialog composition pattern

**Full Dialog pattern** (`TrackedChangesModal.tsx` lines 43-108):
```typescript
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
// + Input (new shadcn dep), LanguageSelect for source/target

// Pattern: controlled open via props (onOpenChange), apply CTA + cancel button in DialogFooter
```

**Key difference from TrackedChangesModal:** Contains form fields (Input + two LanguageSelect) rather than RadioGroup. Form submission calls `POST /api/glossaries` then `queryClient.invalidateQueries({ queryKey: ["glossaries"] })`.

---

### `frontend/src/components/ReviewFilterBar.tsx` (new — component)

**Analog:** `frontend/src/components/StageIndicator.tsx` (horizontal chip strip pattern) — partial match

**Chip active state pattern**: see `NavBar.tsx` active link pattern (`text-violet-600 font-medium`) — adapt for chip with `bg-violet-500 text-white` (active) vs `bg-slate-100 text-slate-700` (inactive). Use `Button` variant="ghost" or plain `<button>` with explicit className.

**Click-to-filter pattern**: each chip carries `onClick` that updates a `FilterState` (lifted to page level via `useState`). The review page passes `activeFilter` + `setActiveFilter` down.

---

### `frontend/src/components/KeyboardHelpPanel.tsx` (new — component)

**Analog:** `frontend/src/components/TrackedChangesModal.tsx` lines 43-108 for Popover/Dialog wrapper pattern

**Popover pattern** (shadcn `Popover` — new dep to add):
```typescript
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Button } from "@/components/ui/button"
import { Keyboard } from "lucide-react"

export function KeyboardHelpPanel() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1 text-xs">
          <Keyboard className="h-3 w-3" /> Shortcuts
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-4">
        {/* 2-column grid of key | action pairs */}
      </PopoverContent>
    </Popover>
  )
}
```

**Deviation from TrackedChangesModal:** Popover (not Dialog) — stays attached to trigger, dismisses on click-outside without needing a full modal overlay. Max-width 320px per UI-SPEC.

---

### `frontend/src/components/UploadForm.tsx` (extend — component, request-response)

**Analog:** self (lines 1-288)

**Extension point** — add `glossaryId` state alongside language state (lines 32-34 pattern):
```typescript
const [glossaryId, setGlossaryId] = useState<string | null>(null)
```

Insert `<GlossarySelect>` after language row (after line 245), before submit button:
```typescript
{sourceLang && sourceLang !== "auto" && targetLang && (
  <div>
    <label className="text-sm text-slate-700">Glossary (optional)</label>
    <GlossarySelect
      sourceLang={sourceLang}
      targetLang={targetLang}
      value={glossaryId}
      onValueChange={setGlossaryId}
      disabled={submitting}
    />
  </div>
)}
```

Extend `submitWithAction` formData append (lines 103-108 pattern):
```typescript
if (glossaryId) {
  formData.append("glossary_id", glossaryId)
}
```

**Deviation:** `canSubmit` guard does NOT require `glossaryId` (it is optional per D-02-24).

---

## Shared Patterns

### FastAPI Dependency Injection
**Source:** `backend/src/app/api/dependencies.py` (lines 1-26)
**Apply to:** all new route files (`glossaries.py`, `segments.py`, `export.py`)

```python
from fastapi import Request
from redis.asyncio import Redis

def get_redis(request: Request) -> Redis:
    return request.app.state.redis

def get_arq_pool(request: Request):
    return request.app.state.arq_pool

def get_settings(request: Request):
    return request.app.state.settings

# Add for Phase 2:
def get_llm_client(request: Request):
    """Returns shared AsyncOpenAI client for synchronous regenerate endpoint."""
    return request.app.state.llm_client
```

### structlog JSON Logging
**Source:** `backend/src/app/api/routes/jobs.py` (line 23: `log = structlog.get_logger()`) + `backend/src/app/workers/translate_worker.py` (line 46)
**Apply to:** `glossary_service.py`, `export_service.py`, `segments.py`, `glossaries.py`

```python
import structlog
log = structlog.get_logger()
# Bind context in service functions:
log.info("glossary_created", glossary_id=g.id, name=g.name)
log.info("terms_imported", glossary_id=glossary_id, imported=N, skipped=M)
log.info("export_complete", job_id=job_id, output_path=output_path)
```

For Phase 2 operations, bind `glossary_id` + `segment_id` context the same way the worker binds `job_id` via `log.bind(...)`.

### HTTPException Error Pattern
**Source:** `backend/src/app/api/routes/jobs.py` (lines 84-87, 107-114, 118-121)
**Apply to:** all new API routes

```python
# 404 pattern (get-or-404):
entity = await service.get_something(session, entity_id)
if entity is None:
    raise HTTPException(status_code=404, detail="Entity not found")

# 409 pattern (state conflict):
raise HTTPException(status_code=409, detail="Job not in exportable state")

# 422 pattern (validation failure):
raise HTTPException(status_code=422, detail="The selected glossary does not match the language pair.")
```

Never expose `str(exc)` in HTTP responses for unhandled exceptions. Log server-side; return generic message.

### Pydantic Frozen Request Models
**Source:** `backend/src/app/llm/schemas.py` pattern (frozen=True, Field constraints)
**Apply to:** all new request body schemas in `segments.py`, `glossaries.py`

```python
from pydantic import BaseModel, Field

class GlossaryCreateRequest(BaseModel, frozen=True):
    name: str = Field(..., min_length=1, max_length=255)
    source_lang: str = Field(..., min_length=1, max_length=64)
    target_lang: str = Field(..., min_length=1, max_length=64)

class TermCreateRequest(BaseModel, frozen=True):
    source_term: str = Field(..., min_length=2, max_length=1000)  # D-02-07: min 2 chars
    target_term: str = Field(..., min_length=2, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
```

### TanStack Query Cache Key Convention
**Source:** `frontend/src/hooks/useJobProgress.ts` lines 34-44 (`queryKey: ["job", jobId]`)
**Apply to:** `useSegments.ts`, glossary query hooks, review page

```typescript
// Established key shapes — follow exactly:
["job", jobId]           // single job — useJobProgress.ts
["jobs"]                 // jobs list — jobs/page.tsx
["languages"]            // languages — LanguageSelect.tsx
// New Phase 2 keys:
["segments", jobId]      // segments for a job — useSegments.ts
["glossaries"]           // all glossaries — GlossaryList
["glossaries", sourceLang, targetLang]  // filtered for picker — GlossarySelect
["glossary", glossaryId]               // single glossary detail
```

### shadcn Dialog Composition
**Source:** `frontend/src/components/TrackedChangesModal.tsx` (lines 43-108)
**Apply to:** `GlossaryCreateDialog.tsx`, delete glossary confirmation dialog

```typescript
// Exact shell to copy:
<Dialog open={open} onOpenChange={open2 => { if (!open2) onCancel(); onOpenChange(open2) }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>...</DialogTitle>
      <DialogDescription>...</DialogDescription>
    </DialogHeader>
    {/* form content */}
    <DialogFooter>
      <Button variant="outline" onClick={onCancel}>Cancel</Button>
      <Button onClick={handleApply}>Confirm</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

### shadcn Table Composition
**Source:** `frontend/src/components/JobsTable.tsx` (lines 35-110)
**Apply to:** `GlossaryList.tsx`, `TermsTable.tsx`

```typescript
// Exact imports and Table shell to copy:
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
// Row hover: className="hover:bg-slate-50 cursor-pointer"
// Actions cell: onClick with e.stopPropagation() to prevent row-level navigation
```

### Next.js 16 Async Params (D-20)
**Source:** `frontend/src/app/jobs/[id]/page.tsx` lines 18-22
**Apply to:** `frontend/src/app/jobs/[id]/review/page.tsx`, `frontend/src/app/glossaries/[id]/page.tsx`

```typescript
// REQUIRED: React.use() to unwrap async params in Next.js 16
import { use } from "react"
export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
```

### Toast Pattern
**Source:** `frontend/src/components/UploadForm.tsx` lines 3-4, 51-53
**Apply to:** all new components that show feedback

```typescript
import { useToast } from "@/hooks/use-toast"
const { toast } = useToast()
// Success:
toast({ description: "Imported 42 terms." })
// Destructive:
toast({ variant: "destructive", description: "Import failed at row 3: missing target_term." })
// Optimistic rollback (useSegments.ts):
toast({ title: "Could not save — edit restored.", variant: "destructive" })
```

---

## No Analog Found

All 27 files have Phase 1 codebase analogs. No files require RESEARCH.md-only patterns as primary source. The RESEARCH.md patterns (Sections 1–9) supplement the codebase analogs with Phase 2-specific logic not present in Phase 1 code — they are secondary references, not primary analogs.

| Capability | Supplementary Reference | Notes |
|------------|------------------------|-------|
| TanStack v5 optimistic mutation | RESEARCH.md Section 1 | No v5 `onMutate` rollback exists in Phase 1; `useJobProgress.ts` is closest but only uses `setQueryData`, not mutations |
| react-virtuoso Virtuoso component | RESEARCH.md Section 2 | No virtualizer used in Phase 1 |
| react-hotkeys-hook useHotkeys | RESEARCH.md Section 3 | No keyboard shortcuts in Phase 1 |
| CSV / TBX parsing stdlib | RESEARCH.md Section 4 | No file format parsing in services in Phase 1 |
| Post-translation violation check | RESEARCH.md Section 5 | New worker extension logic |
| Advisory lock for export | RESEARCH.md Section 7 | New async.Lock pattern; no Phase 1 precedent |
| Single-segment regenerate | RESEARCH.md Section 8 | New synchronous LLM endpoint; Phase 1 only has worker-based translation |

---

## Critical Anti-Patterns (Phase 2 Additions)

These supplement the Phase 1 critical anti-pattern table:

| Anti-Pattern | Files at Risk | Why Forbidden | Correct Alternative |
|--------------|---------------|---------------|---------------------|
| TanStack v4 `onMutate` context shape | `useSegments.ts` | v5: `onMutate(variables)` returns `context`; v4 had different signature | Use `const queryClient = useQueryClient()` captured via closure; return `{ previousSegments }` from `onMutate` |
| `<Virtuoso>` without explicit height | `SegmentTable.tsx` | Collapses to 0px, renders 0 rows with no error | `style={{ height: "calc(100vh - 168px)" }}` always |
| Alembic `native_enum=True` for new enums | `0002_*.py` migration | Creates named PostgreSQL TYPE; `alembic downgrade` fails without manual `DROP TYPE` | `native_enum=False` on all new Phase 2 enums |
| `seg.edited_text or seg.translated_text` for export map | `export_service.py` | `""` (empty string edit) is falsy — Python `or` would skip it and use `translated_text` | `seg.edited_text if seg.edited_text is not None else seg.translated_text or ""` |
| Reassembler changes for Phase 2 | `reassembler.py` | The reassembler receives a pre-resolved `translated_map`; the `edited_text ?? translated_text` logic belongs in `export_service.py`, not the reassembler | Build `translated_map` in caller; pass to reassembler unchanged |
| `window.addEventListener('keydown', ...)` for shortcuts | review page | React 19 Strict Mode double-fires effects; cleanup across re-renders is fiddly | `react-hotkeys-hook` `useHotkeys` with `enableOnFormTags` guard |
| Direct `fetch` for glossary picker in UploadForm | `UploadForm.tsx`, `GlossarySelect.tsx` | Bypasses TanStack cache; re-fetches on every render | `useQuery` with `queryKey: ["glossaries", sourceLang, targetLang]` in `GlossarySelect` |

---

## Metadata

**Analog search scope:** `/home/thu/dev/projects/ai-translation/backend/src/` + `/home/thu/dev/projects/ai-translation/frontend/src/`
**Files scanned:** 40 Python source files + 41 TypeScript/TSX source files = 81 total
**Pattern extraction date:** 2026-04-24
**Primary analogs by category:**
- Backend routes: `jobs.py` (lines 1-128)
- Backend services: `job_service.py` (lines 1-162)
- Backend models: `models.py` (lines 1-123)
- Backend migrations: `e0e8f781ec72_init.py` (lines 1-66)
- Backend worker: `translate_worker.py` (lines 1-end)
- Frontend list pages: `JobsTable.tsx` (lines 1-110) + `jobs/page.tsx`
- Frontend detail pages: `jobs/[id]/page.tsx` (lines 1-166)
- Frontend Select components: `LanguageSelect.tsx` (lines 1-83)
- Frontend Badge components: `StatusBadge.tsx` (lines 1-35)
- Frontend Dialog: `TrackedChangesModal.tsx` (lines 1-108)
- Frontend forms: `UploadForm.tsx` (lines 1-288)
- Frontend hooks: `useJobProgress.ts` (lines 1-45)
- Frontend types: `lib/types.ts` (lines 1-54)
- Frontend layout: `layout.tsx` (lines 1-32)
