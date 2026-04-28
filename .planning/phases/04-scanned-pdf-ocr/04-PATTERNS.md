# Phase 4: Scanned PDF OCR — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 21 new/modified files
**Analogs found:** 19 / 21

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/src/app/pipeline/scanned_pdf/__init__.py` | config | — | `backend/src/app/pipeline/pdf/__init__.py` | exact |
| `backend/src/app/pipeline/scanned_pdf/detector.py` | utility | request-response | `backend/src/app/pipeline/docx/tracked.py` | role-match |
| `backend/src/app/pipeline/scanned_pdf/extractor.py` | service | batch | `backend/src/app/pipeline/pdf/extractor.py` | exact |
| `backend/src/app/pipeline/scanned_pdf/composer.py` | service | batch | `backend/src/app/pipeline/pdf/reassembler.py` | role-match |
| `backend/src/app/pipeline/scanned_pdf/segment_to_md.py` | utility | transform | `backend/src/app/pipeline/pdf/extractor.py` | partial |
| `backend/src/app/pipeline/segment.py` | model | — | self (extend) | exact |
| `backend/src/app/db/models.py` | model | CRUD | self (extend) | exact |
| `backend/src/app/db/migrations/versions/0006_phase4_ocr.py` | migration | — | `backend/src/app/db/migrations/versions/0005_widen_flag_type.py` | exact |
| `backend/src/app/workers/translate_worker.py` | worker | event-driven | self (extend) | exact |
| `backend/src/app/api/routes/upload.py` | route | request-response | self (extend) | exact |
| `backend/src/app/api/routes/segments.py` | route | request-response | self (extend) | exact |
| `backend/Dockerfile` | config | — | existing Dockerfile | exact |
| `backend/pyproject.toml` | config | — | existing pyproject.toml | exact |
| `backend/tests/pipeline/test_scanned_pdf_detector.py` | test | request-response | `backend/tests/pipeline/` (existing) | role-match |
| `backend/tests/pipeline/test_scanned_pdf_extractor.py` | test | batch | existing test pattern | role-match |
| `backend/tests/pipeline/test_scanned_pdf_composer.py` | test | batch | existing test pattern | role-match |
| `backend/tests/pipeline/test_scanned_pdf_roundtrip.py` | test | batch | existing test pattern | role-match |
| `frontend/src/components/SegmentRow.tsx` | component | request-response | self (extend) | exact |
| `frontend/src/components/FlagBadge.tsx` | component | request-response | self (extend) | exact |
| `frontend/src/app/jobs/[id]/review/page.tsx` | component | request-response | self (extend) | exact |
| `frontend/src/components/UploadForm.tsx` | component | request-response | self (extend) | exact |

---

## Pattern Assignments

### `backend/src/app/pipeline/scanned_pdf/detector.py` (utility, request-response)

**Analog:** `backend/src/app/api/routes/upload.py` (text-density heuristic runs at upload time)

**Imports pattern** (upload.py lines 1–29):
```python
from __future__ import annotations
import os
import tempfile
from pathlib import Path
import structlog
import pymupdf
```

**Core pattern** — synchronous detection function called from upload route:
```python
# Pattern from upload.py lines 113–131: temp-file + probe + cleanup
def detect_scanned_pdf(content: bytes, threshold: int = 50) -> bool:
    """
    D-04-17: text-density heuristic.
    Returns True if total_chars / page_count < threshold (scanned PDF).
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        doc = pymupdf.open(tmp_path)
        total_chars = sum(len(page.get_text()) for page in doc)
        page_count = len(doc)
        if page_count == 0:
            return False
        return (total_chars / page_count) < threshold
    finally:
        os.unlink(tmp_path)
```

**Error handling pattern** (upload.py lines 129–131):
```python
# Swallow errors for detection — let worker surface real errors
except Exception:
    pass  # malformed PDF: let worker report actual error; upload proceeds
```

---

### `backend/src/app/pipeline/scanned_pdf/extractor.py` (service, batch)

**Analog:** `backend/src/app/pipeline/pdf/extractor.py`

**Imports pattern** (pdf/extractor.py lines 18–28):
```python
from __future__ import annotations
import unicodedata
import pymupdf
from app.pipeline.segment import Segment
```

**New imports for Phase 4:**
```python
from __future__ import annotations
import asyncio
import unicodedata
from statistics import mean
import structlog
import pymupdf
from app.pipeline.segment import Segment

log = structlog.get_logger()
```

**Core extraction pattern** — mirrors `extract_pdf_segments` structure from pdf/extractor.py lines 470–621:
```python
async def extract_scanned_pdf_segments(
    doc: pymupdf.Document,
    job_id: str,
    pages_dir: str,
    pipeline,   # PPStructureV3 instance (sync, must be wrapped in to_thread)
    dpi: int = 300,
    concurrency: int = 1,
) -> tuple[list[Segment], list[int]]:
    """
    Returns (segments, low_confidence_pages).
    Page images extracted to pages_dir/page-N.png.
    """
    segments: list[Segment] = []
    low_confidence_pages: list[int] = []
    seq = 0

    for page_num, page in enumerate(doc):
        # Step 1: extract page image (D-04-10)
        png_path = os.path.join(pages_dir, f"page-{page_num}.png")
        pixmap = page.get_pixmap(dpi=dpi)
        pixmap.save(png_path)

        # Step 2: D-04-18 mixed-PDF check — use native path if page has text
        if page.get_text().strip():
            # delegate to native pdf extractor for this page
            ...
            continue

        # Step 3: wrap sync PaddleOCR call in asyncio.to_thread
        output = await asyncio.to_thread(pipeline.predict, png_path)

        for res in output:
            json_data = res.json
            parsing_res = json_data.get("layout_parsing_result", {}).get("parsing_res_list", [])
            overall_ocr = json_data.get("overall_ocr_res", {})
            rec_scores = overall_ocr.get("rec_scores", [])
            page_mean_conf = mean(rec_scores) if rec_scores else 1.0

            if page_mean_conf < 0.7:
                low_confidence_pages.append(page_num)

            # D-04-20: trust block_order from PP-StructureV3
            sorted_blocks = sorted(parsing_res, key=lambda b: b.get("block_order") or 0)

            for block in sorted_blocks:
                block_label = block.get("block_label", "text")
                block_content = block.get("block_content", "")
                block_bbox_raw = block.get("block_bbox")  # numpy (4,2)

                # Passthrough labels (D-04-24)
                if block_label in ("image", "chart", "figure", "formula", "formula_number", "algorithm", "seal", "page_number"):
                    ...  # emit figure_passthrough flag or skip
                    continue

                # Normalize bbox from polygon to (x0n, y0n, x1n, y1n) in [0,1]
                x0 = float(block_bbox_raw[:, 0].min())
                y0 = float(block_bbox_raw[:, 1].min())
                x1 = float(block_bbox_raw[:, 0].max())
                y1 = float(block_bbox_raw[:, 1].max())
                page_w = page.rect.width * (dpi / 72.0)
                page_h = page.rect.height * (dpi / 72.0)
                region_bbox = (x0/page_w, y0/page_h, x1/page_w, y1/page_h)

                pos = f"page.{page_num}.region.{block.get('block_id', seq)}"
                segments.append(Segment.from_text(
                    source_text=block_content.strip(),
                    structural_position=pos,
                    seq_in_job=seq,
                    kind="ocr_text",
                    confidence=page_mean_conf,
                    region_bbox=region_bbox,
                    region_label=block_label,
                ))
                seq += 1

    return segments, low_confidence_pages
```

**Error isolation pattern** (mirrors pdf/extractor.py lines 541–547, reassembler.py lines 293–307):
```python
# Per-page isolation (D-04-31)
try:
    output = await asyncio.to_thread(pipeline.predict, png_path)
except Exception as exc:
    log.warning("ocr_page_failed", page=page_num, error=str(exc))
    # Emit placeholder segment; continue job
    segments.append(Segment.from_text(
        source_text="[OCR failed for this page]",
        structural_position=f"page.{page_num}.region.0",
        seq_in_job=seq,
        kind="ocr_text",
        confidence=0.0,
        region_bbox=None,
        region_label=None,
    ))
    seq += 1
    low_confidence_pages.append(page_num)
    continue
```

---

### `backend/src/app/pipeline/scanned_pdf/composer.py` (service, batch)

**Analog:** `backend/src/app/pipeline/pdf/reassembler.py`

**Imports pattern** (reassembler.py lines 28–35):
```python
from __future__ import annotations
import os
import structlog
import pymupdf
from fpdf import FPDF
from app.pipeline.segment import Segment

log = structlog.get_logger()
```

**Core compose pattern** — mirrors `reassemble_pdf` signature (reassembler.py lines 84–104):
```python
def compose_bilingual_pdf(
    segments: list[Segment],
    translated_map: dict[str, str],
    pages_dir: str,
    output_path: str,
    overflow_flags: list[dict],   # out-parameter (same contract as reassembler.py)
    src_doc: pymupdf.Document,
) -> None:
    """
    D-04-07/08/09: double-wide page + left image + right region-positioned text.
    overflow_flags out-parameter: worker reads to persist FlagType.overflow SegmentFlags.
    """
    from fpdf import FPDF  # noqa: PLC0415
    pdf = FPDF(unit="mm")
    pdf.add_font("NotoSans", fname="/backend/fonts/NotoSans-Regular.ttf")
    pdf.add_font("NotoSansCJK", fname="/backend/fonts/NotoSansCJK-Regular.ttc")

    segs_by_page: dict[int, list[Segment]] = {}
    for seg in segments:
        if not seg.structural_position.startswith("page."):
            continue
        page_num = int(seg.structural_position.split(".")[1])
        segs_by_page.setdefault(page_num, []).append(seg)

    for page_num, src_page in enumerate(src_doc):
        src_w_mm = src_page.rect.width / 2.8346
        src_h_mm = src_page.rect.height / 2.8346
        pdf.add_page(format=(2 * src_w_mm, src_h_mm))

        # Left half: original page image
        png_path = os.path.join(pages_dir, f"page-{page_num}.png")
        pdf.image(png_path, x=0, y=0, w=src_w_mm, h=src_h_mm, keep_aspect_ratio=True)

        # Right half: translated text per region
        page_segs = segs_by_page.get(page_num, [])
        for seg in sorted(page_segs, key=lambda s: s.region_bbox[1] if s.region_bbox else 0):
            translated = translated_map.get(seg.id, seg.source_text)
            if seg.region_bbox is None:
                continue
            overflowed = _render_region(pdf, translated, seg.region_bbox, seg.region_label or "text", src_w_mm, src_h_mm)
            if overflowed:
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "auto_adjusted": False,
                    "reason": "min_font_overflow",
                })

    pdf.output(output_path)
```

**Per-block error isolation pattern** (mirrors reassembler.py lines 282–307):
```python
try:
    overflowed = _render_region(pdf, translated, seg.region_bbox, ...)
except Exception as exc:
    log.warning("compose_region_failed", segment_id=seg.id, error=str(exc))
    overflow_flags.append({"segment_id": seg.id, "overflow": True, "auto_adjusted": False, "error": str(exc)})
    continue
```

---

### `backend/src/app/pipeline/scanned_pdf/segment_to_md.py` (utility, transform)

**Analog:** No direct analog — new capability. Closest is `pdf/extractor.py` for its tree-walk pattern.

**Walk pattern** (mirrors pdf/extractor.py lines 492–619 structural_position walk):
```python
from __future__ import annotations
from app.pipeline.segment import Segment

_HEADING_LABELS = frozenset({"doc_title", "paragraph_title"})
_TABLE_LABELS = frozenset({"table"})
_LIST_LABELS = frozenset({"list_item"})

def segments_to_markdown(segments: list[Segment]) -> str:
    """
    D-04-33: Walk Segment tree (by structural_position + region_label)
    → emit Markdown string for DOCX conversion.
    """
    lines: list[str] = []
    # Sort by seq_in_job (extraction order = reading order)
    for seg in sorted(segments, key=lambda s: s.seq_in_job):
        text = seg.edited_text or seg.translated_text or seg.source_text
        label = seg.region_label or "text"
        if label == "doc_title":
            lines.append(f"# {text}")
        elif label in ("paragraph_title",):
            lines.append(f"## {text}")
        elif label in _TABLE_LABELS:
            lines.append(text)  # block_content already Markdown table
        elif seg.kind == "math_passthrough":
            lines.append(text)  # passthrough verbatim
        else:
            lines.append(text)
        lines.append("")  # blank line between blocks
    return "\n".join(lines)
```

---

### `backend/src/app/pipeline/segment.py` (model, extend)

**Analog:** self — extend existing `Segment` dataclass (lines 25–61)

**Current dataclass fields** (segment.py lines 33–44):
```python
@dataclass
class Segment:
    id: str
    seq_in_job: int
    source_text: str
    structural_position: str
    is_comment: bool = False
    is_inserted: bool = False
    is_deleted: bool = False
    translated_text: str | None = None
    run_index: int | None = None
    run_group_size: int = 1
    kind: str = "text"  # "text" | "table_cell" | "math_passthrough"
```

**Phase 4 additions** (D-04-26) — append to existing dataclass:
```python
    # Phase 4 OCR fields (D-04-26)
    confidence: float | None = None          # page-mean or region-mean from PaddleOCR
    region_bbox: tuple[float, float, float, float] | None = None  # [0,1] normalized
    region_label: str | None = None          # PP-StructureV3 block_label
    edited_source_text: str | None = None    # D-04-03: reviewer-corrected OCR source
```

**`from_text` factory** (segment.py lines 46–61) — `**kwargs` already flows new fields:
```python
@classmethod
def from_text(cls, source_text, structural_position, seq_in_job, **kwargs) -> "Segment":
    return cls(
        id=make_segment_id(source_text, structural_position),
        seq_in_job=seq_in_job,
        source_text=source_text,
        structural_position=structural_position,
        **kwargs,   # confidence, region_bbox, region_label, etc. flow here
    )
```

---

### `backend/src/app/db/models.py` (model, extend)

**Analog:** self — extend existing ORM models

**FlagType enum extension pattern** (models.py lines 151–157):
```python
class FlagType(str, enum.Enum):
    overflow = "overflow"
    glossary_violation = "glossary_violation"
    placeholder_mismatch = "placeholder_mismatch"
    llm_refusal = "llm_refusal"
    smartart = "smartart"
    multi_column_degraded = "multi_column_degraded"
    # Phase 4 additions (D-04-26, D-04-24, D-04-31):
    figure_passthrough = "figure_passthrough"
    ocr_page_error = "ocr_page_error"
```

**JobStage enum extension** (models.py lines 24–29):
```python
class JobStage(str, enum.Enum):
    parse = "parse"
    ocr = "ocr"          # Phase 4 new
    translate = "translate"
    compose = "compose"  # Phase 4 new
    reassemble = "reassemble"
    done = "done"
    failed = "failed"
```

**Segment ORM new columns pattern** — follows existing `edited_text` (models.py lines 136–139):
```python
# Phase 4 OCR columns (D-04-29-mig, Alembic 0006)
confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
region_bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # JSONB; [x0,y0,x1,y1] floats
region_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
edited_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Job ORM new input_format value** — `input_format` is already a plain `String(16)` (models.py line 55), so `"scanned_pdf"` is valid immediately without DDL change.

---

### `backend/src/app/db/migrations/versions/0006_phase4_ocr.py` (migration, batch)

**Analog:** `backend/src/app/db/migrations/versions/0005_widen_flag_type.py`

**Migration file structure** (0005 lines 1–51):
```python
"""Phase 4: Add OCR columns to segments; extend JobStage enum.

Adds:
  - segments.confidence: Float nullable
  - segments.region_bbox: JSON nullable
  - segments.region_label: String(64) nullable
  - segments.edited_source_text: Text nullable
  - No DDL for FlagType (VARCHAR, native_enum=False — new values valid immediately)
  - No DDL for input_format (plain String(16) — 'scanned_pdf' valid immediately)
  - JobStage enum: native_enum=False? Check existing — if VARCHAR, no DDL needed.
"""
from __future__ import annotations
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006_phase4_ocr"
down_revision: Union[str, None] = "0005_widen_flag_type"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("segments", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("segments", sa.Column("region_bbox", sa.JSON(), nullable=True))
    op.add_column("segments", sa.Column("region_label", sa.String(64), nullable=True))
    op.add_column("segments", sa.Column("edited_source_text", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("segments", "edited_source_text")
    op.drop_column("segments", "region_label")
    op.drop_column("segments", "region_bbox")
    op.drop_column("segments", "confidence")
```

**Critical note from 0005:** `FlagType` uses `native_enum=False` (VARCHAR storage). New values `figure_passthrough` and `ocr_page_error` are valid immediately as VARCHAR strings. However 0005 taught us that VARCHAR is sized to longest value at table-create time — `figure_passthrough` (17 chars) and `ocr_page_error` (13 chars) both fit in the widened VARCHAR(32). No ALTER needed.

---

### `backend/src/app/workers/translate_worker.py` (worker, event-driven)

**Analog:** self — extend existing `_run_translation` function

**Worker dispatch pattern** (translate_worker.py lines 281–317) — add `scanned_pdf` case:
```python
# Existing match/case (translate_worker.py lines 281–314):
match job.input_format:
    case "docx":
        ...
    case "pptx":
        ...
    case "pdf":
        ...
    # Phase 4 addition:
    case "scanned_pdf":
        import pymupdf  # noqa: PLC0415
        from app.pipeline.scanned_pdf.extractor import extract_scanned_pdf_segments  # noqa: PLC0415
        from app.pipeline.scanned_pdf.detector import PPStructureV3Factory  # noqa: PLC0415
        _pdf_doc = pymupdf.open(job.input_path)
        _pipeline = PPStructureV3Factory.get()  # singleton, baked in Docker (D-04-15)
        pages_dir = os.path.join(data_dir, "jobs", job_id, "pages")
        os.makedirs(pages_dir, exist_ok=True)
        segments, low_confidence_pages = await extract_scanned_pdf_segments(
            _pdf_doc, job_id, pages_dir, _pipeline, dpi=settings.ocr_page_dpi
        )
        _format_ctx = {"type": "scanned_pdf", "doc": _pdf_doc, "pages_dir": pages_dir, "low_confidence_pages": low_confidence_pages}
```

**SSE progress publish pattern** (translate_worker.py lines 192–221):
```python
# Existing _publish_progress signature:
async def _publish_progress(
    redis, job_id, status, stage,
    segments_done, segments_total, current_batch, retry_count, last_message,
    error=None,
) -> None:
    payload = {
        "status": status,
        "stage": stage,
        "segments_done": segments_done,
        "segments_total": segments_total,
        "current_batch": current_batch,
        "retry_count": retry_count,
        "last_message": last_message,
    }
    # Phase 4 addition: stage_progress substructure (D-04-x SSE)
    # Add stage_progress kwarg to _publish_progress and include in payload:
    # "stage_progress": {"stage": stage, "current": segments_done, "total": segments_total}
```

**ORM Segment persist pattern** (translate_worker.py lines 355–384) — extend `SegmentORM` constructor:
```python
# Existing pattern:
orm_segments = [
    SegmentORM(
        id=seg.id, job_id=job_id, seq_in_job=seg.seq_in_job,
        source_text=seg.source_text, structural_position=seg.structural_position,
        ...
    ) for seg in segments
]
# Phase 4: add new fields in the list comprehension:
SegmentORM(
    ...,
    confidence=getattr(seg, "confidence", None),
    region_bbox=list(seg.region_bbox) if getattr(seg, "region_bbox", None) else None,
    region_label=getattr(seg, "region_label", None),
    edited_source_text=None,  # always starts null; reviewer fills in via PATCH
)
```

**Passthrough kind guard** (translate_worker.py line 344) — extend to cover new kinds:
```python
# Existing:
_translatable = [s for s in segments if getattr(s, "kind", "text") != "math_passthrough"]
# Phase 4: figure_passthrough segments also skip LLM (D-04-24):
_SKIP_KINDS = frozenset({"math_passthrough", "figure_passthrough"})
_translatable = [s for s in segments if getattr(s, "kind", "text") not in _SKIP_KINDS]
```

**Reassemble dispatch** (translate_worker.py lines 514–641) — add `scanned_pdf` case:
```python
case "scanned_pdf":
    from app.pipeline.scanned_pdf.composer import compose_bilingual_pdf  # noqa: PLC0415
    _ocr_overflow_flags: list[dict] = []
    output_path = os.path.join(_out_dir, "output.pdf")
    compose_bilingual_pdf(
        segments, translated_map, _format_ctx["pages_dir"],
        output_path, _ocr_overflow_flags, _format_ctx["doc"]
    )
    # Also produce translated-only PDF and DOCX (D-04-22)...
    # Persist overflow flags (same pattern as case "pdf" lines 595–641)
```

**Per-stage retry pattern** (D-04-30) — mirrors the existing `translate_batch_with_retry` (translate_worker.py lines 111–184):
```python
_OCR_MAX_RETRIES = 2
_COMPOSE_MAX_RETRIES = 2

async def _run_with_retry(fn, *args, max_retries: int, label: str, job_id: str, **kwargs):
    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            if attempt + 1 == max_retries:
                raise
            wait = 2.0 ** (attempt + 1)
            log.warning(f"{label}_retry", job_id=job_id, attempt=attempt+1, wait_s=wait, error=str(exc))
            await asyncio.sleep(wait)
```

---

### `backend/src/app/api/routes/upload.py` (route, request-response)

**Analog:** self — extend existing upload route

**Existing Form field pattern** (upload.py lines 41–51):
```python
@router.post("/upload", status_code=202)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    tracked_changes_action: str | None = Form(None),
    glossary_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    arq_pool=Depends(get_arq_pool),
) -> dict:
```

**Phase 4 addition** — add `is_scanned_override` (D-04-17):
```python
    is_scanned_override: bool | None = Form(None),  # None = auto-detect; True/False = user override
```

**Scanned-PDF detection insertion point** — after extension check, before Job create:
```python
# D-04-17: auto-detect scanned PDF; user override wins
is_scanned = False
if ext == ".pdf":
    from app.pipeline.scanned_pdf.detector import detect_scanned_pdf  # noqa: PLC0415
    if is_scanned_override is not None:
        is_scanned = is_scanned_override
    else:
        is_scanned = detect_scanned_pdf(content, threshold=settings.ocr_text_density_threshold)

# Adjust input_format for job creation
effective_format = "scanned_pdf" if (ext == ".pdf" and is_scanned) else ext.lstrip(".")
```

**Response extension**:
```python
return {
    "job_id": job.id,
    "has_tracked_changes": has_tracked,
    "is_scanned": is_scanned,          # Phase 4: inform frontend for UI badge
}
```

---

### `backend/src/app/api/routes/segments.py` (route, request-response)

**Analog:** self — extend existing PATCH and serializers

**SegmentPatchRequest extension** (segments.py lines 32–34):
```python
class SegmentPatchRequest(BaseModel, frozen=True):
    edited_text: str | None = Field(default=..., max_length=10_000)
    # Phase 4 addition (D-04-12):
    edited_source_text: str | None = Field(default=None, max_length=10_000)
```

**`_segment_to_dict` serializer extension** (segments.py lines 53–63):
```python
def _segment_to_dict(s: Segment) -> dict:
    return {
        "id": s.id,
        "seq_in_job": s.seq_in_job,
        "source_text": s.source_text,
        "translated_text": s.translated_text,
        "edited_text": s.edited_text,
        "expansion_ratio": s.expansion_ratio,
        "structural_position": s.structural_position,
        "flags": [_flag_to_dict(f) for f in (s.flags or [])],
        # Phase 4 additions:
        "confidence": getattr(s, "confidence", None),
        "region_bbox": getattr(s, "region_bbox", None),
        "region_label": getattr(s, "region_label", None),
        "edited_source_text": getattr(s, "edited_source_text", None),
    }
```

**PATCH handler extension** (segments.py lines 140–147):
```python
values_to_update: dict = {}
if body.edited_text is not ...:
    values_to_update["edited_text"] = body.edited_text
if body.edited_source_text is not None:
    values_to_update["edited_source_text"] = body.edited_source_text

await session.execute(
    update(Segment)
    .where(Segment.job_id == job_id, Segment.id == segment_id)
    .values(**values_to_update)
)
```

**Regenerate endpoint extension** (segments.py lines 180–189) — use `edited_source_text ?? source_text` (D-04-25):
```python
# D-04-25: use corrected OCR source if available
source_for_regen = (
    seg.edited_source_text if getattr(seg, "edited_source_text", None) else seg.source_text
)
translated_list = await translate_batch(
    client=llm_client,
    segments=[source_for_regen],   # was: [seg.source_text]
    source_lang=job.source_lang,
    target_lang=job.target_lang,
    glossary=glossary,
)
```

---

### `frontend/src/components/SegmentRow.tsx` (component, request-response)

**Analog:** self — extend existing SegmentRow

**FlagType record extension pattern** (SegmentRow.tsx lines 12–19):
```typescript
// Existing FLAG_BADGE_STYLES pattern — extend with Phase 4 types:
const FLAG_BADGE_STYLES: Record<FlagType, string> = {
  overflow: "bg-amber-100 text-amber-800 border-amber-300",
  glossary_violation: "bg-violet-100 text-violet-800 border-violet-300",
  placeholder_mismatch: "bg-orange-100 text-orange-800 border-orange-300",
  llm_refusal: "bg-red-100 text-red-800 border-red-300",
  smartart: "bg-orange-100 text-orange-800 border-orange-300",
  multi_column_degraded: "bg-slate-100 text-slate-600 border-slate-300",
  // Phase 4 additions:
  figure_passthrough: "bg-slate-100 text-slate-500 border-slate-200",
  ocr_page_error: "bg-red-100 text-red-800 border-red-300",
};
```

**Source cell double-click pattern** (D-04-12) — mirrors existing target cell textarea (SegmentRow.tsx lines 186–233):
```typescript
// Source cell: double-click to edit (D-04-12)
const [sourceEditing, setSourceEditing] = useState(false);
const [localSourceValue, setLocalSourceValue] = useState(
  segment.edited_source_text ?? segment.source_text
);
const sourceDebounceRef = useRef<ReturnType<typeof setTimeout>>();
const patchMutation = useSegmentPatch(jobId);  // reuse existing mutation

// In JSX, replace existing read-only source div with:
<div
  className="flex-[40] py-2 px-2 ..."
  onDoubleClick={() => setSourceEditing(true)}
>
  {sourceEditing ? (
    <Textarea
      value={localSourceValue}
      onChange={(e) => {
        setLocalSourceValue(e.target.value);
        clearTimeout(sourceDebounceRef.current);
        sourceDebounceRef.current = setTimeout(() => {
          patchMutation.mutate({ segmentId: segment.id, editedText: null, editedSourceText: e.target.value });
        }, 500);
      }}
      onBlur={() => setSourceEditing(false)}
      autoFocus
    />
  ) : (
    <>{segment.edited_source_text ?? segment.source_text}</>
  )}
</div>
```

**Confidence chip pattern** (D-04-13) — mirrors existing InlineFlagBadge:
```typescript
// Confidence chip in row gutter — add to existing flag cell div
function ConfidenceChip({ confidence }: { confidence: number | null }) {
  if (confidence === null) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 70 ? "text-green-700 bg-green-50 border-green-200"
    : pct >= 50 ? "text-amber-700 bg-amber-50 border-amber-200"
    : "text-red-700 bg-red-50 border-red-200";
  return (
    <span className={cn("inline-block text-[10px] px-1.5 py-0.5 rounded border leading-tight", color)}>
      {pct}%
    </span>
  );
}
```

**Image crop click-to-expand** (D-04-11) — uses react-virtuoso variable row height (already supported per D-02-16):
```typescript
const [imageExpanded, setImageExpanded] = useState(
  (segment.confidence ?? 1) < 0.7  // D-04-11: auto-expand low-confidence
);

// In JSX — collapsible crop above source/target cells:
{imageExpanded && segment.region_bbox && (
  <div className="w-full border-b border-slate-100 bg-slate-50 overflow-hidden">
    <img
      src={`/api/jobs/${jobId}/pages/${pageNum}.png`}
      style={{
        // CSS clip using region_bbox [0,1] normalized → % viewport
        objectFit: "none",
        objectPosition: `-${segment.region_bbox[0] * 100}% -${segment.region_bbox[1] * 100}%`,
        width: `${(segment.region_bbox[2] - segment.region_bbox[0]) * 100}%`,
      }}
      alt="OCR region"
    />
  </div>
)}
```

---

### `frontend/src/components/FlagBadge.tsx` (component, request-response)

**Analog:** self — extend existing FLAG_CONFIG

**Extension pattern** (FlagBadge.tsx lines 5–12):
```typescript
const FLAG_CONFIG: Record<FlagType, { label: string; className: string }> = {
  overflow:             { label: "Overflow",     className: "text-amber-600 bg-amber-50 border-amber-200" },
  glossary_violation:   { label: "Glossary",     className: "text-violet-700 bg-violet-50 border-violet-200" },
  placeholder_mismatch: { label: "Placeholder",  className: "text-orange-700 bg-orange-50 border-orange-200" },
  llm_refusal:          { label: "Refusal",      className: "text-red-700 bg-red-50 border-red-200" },
  smartart:             { label: "SMART",         className: "text-orange-700 bg-orange-50 border-orange-200" },
  multi_column_degraded:{ label: "MULTI-COL",    className: "text-slate-600 bg-slate-100 border-slate-300" },
  // Phase 4 additions:
  figure_passthrough:   { label: "FIGURE",        className: "text-slate-500 bg-slate-50 border-slate-200" },
  ocr_page_error:       { label: "OCR-ERR",       className: "text-red-700 bg-red-50 border-red-200" },
}
```

**Type union extension** — also update `FlagType` in `frontend/src/lib/review-types.ts` (lines 5–11):
```typescript
export type FlagType =
  | "overflow"
  | "glossary_violation"
  | "placeholder_mismatch"
  | "llm_refusal"
  | "smartart"
  | "multi_column_degraded"
  | "figure_passthrough"    // Phase 4
  | "ocr_page_error";       // Phase 4
```

---

### `frontend/src/app/jobs/[id]/review/page.tsx` (component, request-response)

**Analog:** self — extend existing review page

**Needs-review banner pattern** (D-04-14) — insert above `<ReviewFilterBar>`:
```typescript
// Job type extended with low_confidence_pages: number[]
// Banner renders if job.low_confidence_pages?.length > 0

{job?.low_confidence_pages && job.low_confidence_pages.length > 0 && (
  <div className="mx-4 mb-2 p-3 bg-amber-50 border border-amber-200 rounded text-sm text-amber-800">
    <strong>Low OCR confidence:</strong>{" "}
    Pages {job.low_confidence_pages.map((n) => (
      <button
        key={n}
        className="underline mx-0.5 hover:text-amber-900"
        onClick={() => {
          // Jump to first segment of page N via structural_position breadcrumb "page.N."
          const idx = filteredSegments.findIndex(
            (s) => s.structural_position?.startsWith(`page.${n}.`)
          );
          if (idx >= 0) handleFocusChange(idx);
        }}
      >
        {n + 1}
      </button>
    ))}{" "}
    — verify before export.
  </div>
)}
```

**SSE payload extension** — update `JobProgress` type in `frontend/src/lib/types.ts` to include `stage_progress`:
```typescript
// Existing JobProgress type — add:
stage_progress?: {
  stage: string;
  current: number;
  total: number;
};
low_confidence_pages?: number[];
```

---

### `frontend/src/components/UploadForm.tsx` (component, request-response)

**Analog:** self — extend existing UploadForm

**Scanned PDF override toggle pattern** (D-04-17) — mirrors existing `trackedAction` state pattern (UploadForm.tsx lines 40–45):
```typescript
// New state after existing trackedAction state:
const [isScannedDetected, setIsScannedDetected] = useState<boolean | null>(null)
const [isScannedOverride, setIsScannedOverride] = useState<boolean | null>(null)

// After file upload response parsing (extends existing response handling):
const data = await res.json()
if (data.is_scanned !== undefined) {
  setIsScannedDetected(data.is_scanned)
}
```

**Override UI** — insert after drop zone, visible only for PDF files:
```tsx
{file && getExt(file.name) === ".pdf" && isScannedDetected !== null && (
  <div className="text-sm text-slate-600 flex items-center gap-2">
    <span>
      Detected: {isScannedDetected ? "scanned PDF" : "native PDF"}
    </span>
    <button
      type="button"
      className="underline text-indigo-600 text-xs"
      onClick={() => setIsScannedOverride(v => v === null ? !isScannedDetected : null)}
    >
      {isScannedOverride !== null ? "Reset to auto" : "Change"}
    </button>
  </div>
)}
```

**Form submission** — extend `formData.append` block (UploadForm.tsx lines 105–110):
```typescript
const effectiveScanned = isScannedOverride !== null ? isScannedOverride : isScannedDetected
if (effectiveScanned !== null) {
  formData.append("is_scanned_override", String(effectiveScanned))
}
```

---

### `frontend/src/hooks/useJobProgress.ts` (hook, request-response)

**Analog:** self — extend existing SSE hook

**Stage progress rendering** (D-04-x SSE) — existing `useJobProgress` (useJobProgress.ts lines 17–29) passes data directly to `queryClient.setQueryData`. The `stage_progress` field flows through automatically once added to the `JobProgress` type. Frontend components read it directly from `job.stage_progress`.

```typescript
// In job progress display component (StageIndicator.tsx or similar):
// job.stage_progress?.stage === "ocr" → "OCR'd {current}/{total} pages"
// job.stage_progress?.stage === "translate" → "Translated {current}/{total} segments"
// job.stage_progress?.stage === "compose" → "Composing page {current}/{total}"
```

---

### Test files (backend/tests/pipeline/test_scanned_pdf_*.py)

**Analog:** Existing test pattern from Phase 1 (mock LLM + real pipeline calls)

**Mock PaddleOCR pattern** (D-04-28) — mirrors the existing mock pattern in worker tests:
```python
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_ppstructurev3():
    """Canned parsing_res_list with confidence scores."""
    mock_res = MagicMock()
    mock_res.json = {
        "layout_parsing_result": {
            "parsing_res_list": [
                {
                    "block_bbox": _make_bbox(10, 10, 200, 40),  # numpy-like
                    "block_label": "paragraph_title",
                    "block_content": "Tiêu đề",
                    "block_id": 0,
                    "block_order": 0,
                },
                {
                    "block_bbox": _make_bbox(10, 50, 400, 150),
                    "block_label": "text",
                    "block_content": "Nội dung đoạn văn.",
                    "block_id": 1,
                    "block_order": 1,
                },
            ]
        },
        "overall_ocr_res": {"rec_scores": [0.95, 0.88, 0.92]},
    }
    mock_pipeline = MagicMock()
    mock_pipeline.predict.return_value = [mock_res]
    return mock_pipeline
```

**Integration test marker** (D-04-28):
```python
@pytest.mark.integration
async def test_real_ocr_vn_fixture(tmp_path):
    """Real PaddleOCR + DashScope on vn-typed.pdf fixture."""
    ...
```

---

## Shared Patterns

### structlog with bound job context
**Source:** `backend/src/app/workers/translate_worker.py` lines 57–58 and `backend/src/app/core/logging.py`
**Apply to:** `extractor.py`, `composer.py`, `segment_to_md.py`, worker extension

```python
import structlog
log = structlog.get_logger()

# Per-page context binding (extend Phase 1 bind_job_id pattern):
log.info("ocr_page_complete", page=page_num, conf=round(page_mean_conf, 3), segments=len(page_segments))
log.warning("ocr_page_failed", page=page_num, error=str(exc))
```

### asyncio.to_thread for sync I/O in async workers
**Source:** arq worker pattern (translate_worker.py uses asyncio.Semaphore similarly)
**Apply to:** `extractor.py` PaddleOCR call, `composer.py` fpdf2 compose call

```python
# Wrap sync PaddleOCR predict() to avoid blocking arq event loop:
output = await asyncio.to_thread(pipeline.predict, png_path)

# Wrap sync fpdf2 PDF write if it is CPU-heavy:
await asyncio.to_thread(pdf.output, output_path)
```

### SegmentFlag persistence (out-parameter pattern)
**Source:** `backend/src/app/workers/translate_worker.py` lines 574–641
**Apply to:** composer.py overflow_flags out-parameter, worker `case "scanned_pdf"` flag persist

```python
# Existing pattern (translate_worker.py lines 596–617):
_pdf_db_flags: list[SegmentFlag] = []
for _r in _pdf_overflow_flags:
    _seg_id = _r["segment_id"]
    _details = {k: v for k, v in _r.items() if k != "segment_id"}
    if _r.get("overflow"):
        _pdf_db_flags.append(SegmentFlag(
            segment_id=_seg_id,
            segment_job_id=job_id,
            flag_type=FlagType.overflow,
            severity=FlagSeverity.warn,
            details=_details,
        ))
if _pdf_db_flags:
    session.add_all(_pdf_db_flags)
    await session.flush()
```

### Immutable dataclass extension (Pydantic frozen + dataclass)
**Source:** `backend/src/app/pipeline/segment.py` + global `coding-style.md`
**Apply to:** `Segment` dataclass extension (D-04-26)
```python
# Phase 4 fields use `| None = None` pattern (same as existing kind, translated_text)
# NEVER mutate segment fields — always create new Segment via from_text() factory
```

### TanStack optimistic mutation (onMutate → rollback)
**Source:** `frontend/src/hooks/useSegments.ts` lines 40–68 (`useSegmentPatch`)
**Apply to:** new `useSegmentPatchSource` hook (or extend existing `useSegmentPatch`)

```typescript
// Existing onMutate pattern (useSegments.ts lines 40–51):
onMutate: async ({ segmentId, editedText }) => {
  await queryClient.cancelQueries({ queryKey: ["segments", jobId] });
  const previousSegments = queryClient.getQueryData<Segment[]>(["segments", jobId]);
  queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
    old?.map((seg) =>
      seg.id === segmentId ? { ...seg, edited_text: editedText } : seg
    ) ?? []
  );
  return { previousSegments };
},
// Phase 4: extend same pattern for edited_source_text field
```

### Debounced PATCH (500ms, isMountedRef guard)
**Source:** `frontend/src/components/SegmentRow.tsx` lines 110–133
**Apply to:** source-cell edit (D-04-12) in SegmentRow

```typescript
// Exact debounce pattern to reuse:
const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
const handleChange = (value: string) => {
  clearTimeout(debounceRef.current);
  debounceRef.current = setTimeout(() => {
    patchMutation.mutate({ segmentId: segment.id, editedText: value });
  }, 500);
};
// isMountedRef guard (lines 135–141) prevents stale setState after unmount
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/src/app/pipeline/scanned_pdf/segment_to_md.py` | utility | transform | Markdown emission from a Segment tree is new — no existing MD writer in codebase. Closest is `pdf/extractor.py` for its tree-walk, but the output target is entirely different. Use python-docx 1.2.0 (already in stack) as the DOCX write-out target rather than PP-StructureV3 save_to_word (per RESEARCH.md §DOCX path recommendation). |

---

## Metadata

**Analog search scope:** `backend/src/app/pipeline/`, `backend/src/app/workers/`, `backend/src/app/api/routes/`, `backend/src/app/db/`, `frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/lib/`
**Files scanned:** 27
**Pattern extraction date:** 2026-04-28
