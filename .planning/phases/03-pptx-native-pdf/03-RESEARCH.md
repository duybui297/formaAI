# Phase 3: PPTX + Native PDF — Research

**Researched:** 2026-04-25
**Domain:** python-pptx 1.0.2 (PPTX traversal/reassembly), PyMuPDF 1.27.x (PDF redact-reinsert)
**Confidence:** HIGH (stack is well-documented; specific API behaviors verified via Context7 + official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-03-01** SmartArt UX: Segment row + `smartart` flag (orange) — translate but skip write-back, manual copy/paste
- **D-03-02** PPTX overflow auto-fit: apply `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` only when shrink ≥ 0.7 of source font size; else flag overflow
- **D-03-03** PDF column clustering: 2 dense x-clusters + gap ≥ 30% page width → 2-col reading; 3+ clusters or ambiguous → flag `multi_column_degraded` + flat read
- **D-03-04** PDF font: bundled Noto Sans + Noto Sans CJK (already in Docker image via apt)
- **D-03-05** PDF non-text: pass through untouched via `apply_redactions()`
- **D-03-06** PDF column preservation: HTML round-trip — `page.get_text("html")` → translate inline → `insert_htmlbox()`
- **D-03-07** Review UI breadcrumb: `font-mono text-xs` badge in source cell; PPTX `Slide N / Shape M / ¶K`, PDF `Page N / Col M / Block K`

### Carry-forward (locked, no re-decide)
- Segment tree + `make_segment_id` (sha256[:16])
- Compound PK (job_id, id) on segments table
- `run_post_check(..., job_id=...)` signature unchanged
- `pack_into_batches()` + `terminology` injection per batch
- Paper-skill fonts: Roboto / Montserrat / JetBrains Mono

### Claude's Discretion
- Exact column-clustering algorithm implementation (threshold locked, algorithm not)
- Master-slide deduplication strategy
- SmartArt XML detection order (primary + fallback)
- Structural position string conventions for groups/tables (examples given in CONTEXT.md)

### Deferred Ideas (OUT OF SCOPE)
- Scanned PDFs / OCR (Phase 4)
- 3+ column PDF intelligent clustering (v2)
- Original-font fidelity beyond Noto
- RTL language exercise (Arabic/Hebrew)
- pdf2docx round-trip as primary path
- VLM image-text extraction
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PPTX-01 | PPTX round-trips with text boxes, speaker notes, tables, bulleted lists, master text translated | Q1 (group walk), Q5 (notes), Q6 (table), Q3 (master dedup) |
| PPTX-02 | SmartArt shapes detected + flagged, not silently skipped | Q2 (SmartArt detection) |
| PPTX-03 | Text-box overflow detected and flagged; auto-fit applied where safe | Q4 (overflow measurement), D-03-02 (threshold) |
| PPTX-04 | Group-shape walker recursively finds text in nested grouped shapes | Q1 (group recursion) |
| PDF-01 | Native PDF parsed with PyMuPDF; span bbox/font/size captured | Q7 (block extraction) |
| PDF-02 | Translated PDF produced via redact-annot workflow with Noto fonts | Q11 (workflow), Q12 (font CSS) |
| PDF-03 | Overflow: font scaled within safe range; else flagged | Q9 (insert_htmlbox overflow detection) |
| PDF-04 | Multi-column: column-clustering heuristic proven on 2-col PDF | Q10 (clustering algorithm) |
| LAYOUT-02 | Format-specific overflow detectors run post-translation; set flags | Q4, Q9 |
| LAYOUT-03 | Auto-fit applied conservatively; recorded as auto-adjusted in segment metadata | D-03-02, Q4 |
</phase_requirements>

---

## Executive Summary

Five things the planner must know before writing tasks:

1. **PPTX group walk is clean:** `GroupShape.shapes` is the standard python-pptx API for iterating group children. Recursion terminates because `shape.shape_type == MSO_SHAPE_TYPE.GROUP` only fires on true group containers — python-pptx never exposes the slide's spTree as a GroupShape. No cycle-detection needed.

2. **SmartArt has a first-class enum:** `MSO_SHAPE_TYPE.IGX_GRAPHIC` is the definitive type value for SmartArt. Use it as primary; the XML `graphicData uri` contains `"diagram"` as a reliable secondary check. The CONTEXT.md heuristic (`shape.element.findall(".//{*}graphicFrame")`) is a fallback for edge cases.

3. **`insert_htmlbox` returns a tuple `(spare_height, scale)`:** `spare_height == -1` and `scale == scale_low` means fitting failed. By default `scale_low=0` so the method always scales down to fit; to detect overflow you must set `scale_low` to your minimum acceptable scale (0.7 per D-03-02) and check whether the returned `scale` equals `scale_low`.

4. **HTML round-trip is block-level, not whole-page:** Extract blocks via `page.get_text("dict")["blocks"]` for segmentation and column clustering. For the actual HTML source to reinsert, use `page.get_text("html", clip=block_bbox)` per-block. The `clip` parameter restricts text to the block's bounding box. Note: `clip` does NOT affect `html` output format per docs — use `get_text("rawdict", clip=rect)` for structured data and `get_text("html")` only whole-page, then filter spans by bbox.

5. **New packages not yet in pyproject.toml:** `pymupdf>=1.26` and `python-pptx==1.0.2` (already in CLAUDE.md stack but absent from `backend/pyproject.toml`). Both must be added before Phase 3 implementation starts. `python-pptx 1.0.2` has breaking changes from 0.6.x — do not downgrade.

**Primary recommendation:** Build PPTX extractor and PDF extractor as independent modules in `pipeline/pptx/` and `pipeline/pdf/` that share the existing `Segment` dataclass. The worker dispatch is a match/case on `job.input_format`. No `Pipeline` Protocol abstraction needed for PoC scope.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PPTX text extraction | API/Backend (worker) | — | File I/O + CPU-bound parsing runs in arq worker |
| PPTX SmartArt detection | API/Backend (worker) | — | XML inspection at parse time in extractor |
| PPTX overflow detection | API/Backend (worker) | — | Runs post-translate in run_post_check extension |
| PPTX reassembly | API/Backend (worker) | — | In-memory document mutation, save to disk |
| PDF block extraction | API/Backend (worker) | — | PyMuPDF bindings, CPU-bound |
| PDF column clustering | API/Backend (worker) | — | Pure numeric algorithm on block bboxes |
| PDF redact-reinsert | API/Backend (worker) | — | PyMuPDF page mutation |
| Breadcrumb rendering | Frontend (SegmentRow) | — | Pure display transform of structural_position string |
| FlagBadge extension | Frontend (FlagBadge, SegmentRow) | — | Extend existing FLAG_CONFIG records |
| UploadForm accept list | Frontend (UploadForm) | — | Surgical change to accept attribute |
| FlagType enum extension | DB model (backend) | Frontend types | `FlagType` enum in models.py + FlagType union in lib/types.ts |

---

## Standard Stack

### Core (additions to pyproject.toml — not yet added)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pymupdf` | `>=1.26,<2` (latest: 1.27.2.3) | PDF extraction + redact-reinsert + insert_htmlbox | Only OSS Python PDF library with both read and write (text insertion) API |
| `python-pptx` | `==1.0.2` | PPTX read/write: shapes, text frames, tables, notes | Official OOXML Python library; version pinned per CLAUDE.md |

### Already in pyproject.toml (carry-forward)
| Library | Version | Purpose |
|---------|---------|---------|
| `python-docx` | `==1.2.0` | DOCX (Phase 1 — untouched) |
| All arq/SQLAlchemy/FastAPI deps | existing | Unchanged |

**Installation (uv):**
```bash
cd backend
uv add "pymupdf>=1.26,<2" "python-pptx==1.0.2"
```

**Fonts (already in Docker — verify):**
```dockerfile
RUN apt-get install -y fonts-noto-cjk fonts-noto && fc-cache -f
```
Noto fonts path on Debian/Ubuntu: `/usr/share/fonts/truetype/noto/`

---

## Architecture Patterns

### System Architecture Diagram

```
Upload (PPTX / native PDF)
         │
         ▼
  arq worker: translate_job()
         │
    match job.input_format:
     ├── "docx" ──► existing path (untouched)
     ├── "pptx" ──► pipeline/pptx/extractor.py
     │                    │
     │              walk_presentation()
     │              ├── master shapes (once per master)
     │              ├── slides[N].shapes → recursive walk_shape_tree()
     │              │    ├── text frames → Segment
     │              │    ├── tables → cell text frames → Segment
     │              │    ├── groups → recurse
     │              │    ├── SmartArt (IGX_GRAPHIC) → Segment + smartart flag
     │              │    └── notes_slide.notes_text_frame → Segment
     │              └── → list[Segment]
     │                         │
     │              pack_into_batches() → translate → translated_map
     │                         │
     │              pipeline/pptx/reassembler.py
     │              ├── write translated text back by structural_position
     │              ├── SmartArt: skip write-back (flag already set)
     │              ├── overflow detection → MSO_AUTO_SIZE if shrink ≥ 0.7
     │              └── → output .pptx bytes → save to disk
     │
     └── "pdf" ──► pipeline/pdf/extractor.py
                        │
                  for each page:
                    blocks = page.get_text("dict")["blocks"]
                    columns.py: cluster x-midpoints
                    ├── 2-col: assign blocks to col 0 / col 1, reading order
                    └── 3+-col or ambiguous: flat order + multi_column_degraded flag
                    → list[Segment] with structural_position
                         │
                  pack_into_batches() → translate → translated_map
                         │
                  pipeline/pdf/reassembler.py
                  for each page:
                    for each block_segment:
                      page.add_redact_annot(block_bbox, fill=bg_color)
                    page.apply_redactions(images=PDF_REDACT_IMAGE_NONE)
                    for each block_segment:
                      page.insert_htmlbox(block_bbox, translated_html,
                                         css=noto_css, archive=arch)
                      if spare_height < 0: flag overflow
                  → doc.save() → output .pdf bytes
```

### Recommended Project Structure
```
backend/src/app/pipeline/
├── segment.py                   # existing — no changes
├── docx/                        # existing — no changes
│   ├── extractor.py
│   ├── reassembler.py
│   └── tracked.py
├── pptx/
│   ├── __init__.py
│   ├── extractor.py             # walk_presentation() → list[Segment]
│   ├── reassembler.py           # write translations back into Presentation
│   └── smartart.py              # is_smartart() detection helper
└── pdf/
    ├── __init__.py
    ├── extractor.py             # page block extraction → list[Segment]
    ├── reassembler.py           # redact-reinsert per block
    ├── columns.py               # cluster_columns() heuristic
    └── fonts.py                 # build_noto_css() + pymupdf.Archive for Noto

frontend/src/
├── lib/
│   ├── types.ts                 # add smartart, multi_column_degraded to FlagType
│   └── formatBreadcrumb.ts      # new: pure helper, prefix-based detection
└── components/
    ├── FlagBadge.tsx            # extend FLAG_CONFIG (2 entries)
    ├── SegmentRow.tsx           # add breadcrumb render above source text
    └── UploadForm.tsx           # extend accept list, update copy
```

---

## Research Questions — Answers

### Q1: Group Shape Recursion (PPTX-04)

**python-pptx API:** `GroupShape.shapes` exposes children exactly like `Slide.shapes`. The group shape type is `MSO_SHAPE_TYPE.GROUP`. No infinite-loop risk — the slide's root spTree is exposed as `slide.shapes` (type `SlideShapes`), not as a `GroupShape`.

[VERIFIED: Context7 /scanny/python-pptx — GroupShape, Shape Access docs]

**Recursive walker with stable structural_position:**

```python
from pptx.enum.shapes import MSO_SHAPE_TYPE
from collections.abc import Iterator
from app.pipeline.segment import Segment

def walk_shape_tree(
    shapes,
    slide_idx: int,
    seq: list[int],  # mutable counter [current_seq]
    pos_prefix: str,  # e.g. "slide.3"
) -> Iterator[Segment]:
    for shape_idx, shape in enumerate(shapes):
        shape_pos = f"{pos_prefix}.shape.{shape_idx}"

        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            # Recurse: GroupShape.shapes gives children
            yield from walk_shape_tree(
                shape.shapes,
                slide_idx,
                seq,
                f"{shape_pos}.group",  # e.g. "slide.3.shape.2.group"
            )

        elif is_smartart(shape):
            # D-03-01: extract text best-effort, flag smartart, skip reassembly
            text = _extract_smartart_text(shape)
            if text.strip():
                yield Segment.from_text(
                    source_text=text,
                    structural_position=f"{shape_pos}.smartart",
                    seq_in_job=seq[0],
                    # flag added in run_post_check extension or at extract time
                )
                seq[0] += 1

        elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            yield from walk_table(shape.table, shape_pos, seq)

        elif shape.has_text_frame:
            yield from walk_text_frame(
                shape.text_frame, shape_pos, seq
            )
```

**Notes:**
- `shape.has_text_frame` is False for GROUP, TABLE, PICTURE — safe guard
- Tables are accessed via `shape.shape_type == MSO_SHAPE_TYPE.TABLE` → `shape.table`
- SmartArt (`IGX_GRAPHIC`) does NOT have `has_text_frame = True` in python-pptx, but text CAN be extracted from the XML (see Q2)
- Position convention for nested group: `slide.N.shape.M.group.shape.S.tf.0.para.K`

### Q2: SmartArt Detection (PPTX-02)

**Definitive check:** `shape.shape_type == MSO_SHAPE_TYPE.IGX_GRAPHIC` — this is the exact enum value for SmartArt in python-pptx. It is NOT `DIAGRAM` (that maps to a different value). [VERIFIED: Context7 /scanny/python-pptx — MSO_SHAPE_TYPE enumeration]

**Secondary XML check (fallback for edge cases):**
```python
SMARTART_URI = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
TABLE_URI = "http://schemas.openxmlformats.org/drawingml/2006/table"
CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"

def is_smartart(shape) -> bool:
    # Primary: python-pptx enum (most reliable)
    if shape.shape_type == MSO_SHAPE_TYPE.IGX_GRAPHIC:
        return True
    # Fallback: XML inspection (catches malformed/unlabeled SmartArt)
    graphic_data = shape.element.findall(
        ".//{http://schemas.openxmlformats.org/drawingml/2006/main}graphicData"
    )
    return any(
        gd.get("uri") == SMARTART_URI
        for gd in graphic_data
    )
```

**Key:** Table `graphicData` URI ends in `/table`, chart ends in `/chart`, SmartArt ends in `/diagram`. All three live inside `p:graphicFrame/a:graphic/a:graphicData`. [VERIFIED: Context7 /scanny/python-pptx — graphicFrame XML analysis docs]

**Text extraction from SmartArt (best-effort):**
```python
def _extract_smartart_text(shape) -> str:
    # SmartArt XML: dgm:treeNode/.../a:t elements
    from lxml import etree
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    texts = shape.element.findall(".//a:t", ns)
    return " ".join(t.text for t in texts if t.text)
```

### Q3: Master-Slide Deduplication

**Access pattern:**
```python
# prs.slide_master is the first master; prs.slide_masters for all
master = prs.slide_master
for shape in master.shapes:
    if shape.has_text_frame:
        # translate once per (master_id, shape_idx) key
        pass

# Per slide: slide.slide_layout.slide_master gives the master this slide uses
```

**Deduplication strategy:**

```python
# In the extractor, maintain a set across the presentation:
_master_segment_ids: set[str] = set()

def extract_master_segments(prs, seq: list[int]) -> list[Segment]:
    segments = []
    for master_idx, master in enumerate(prs.slide_masters):
        for shape_idx, shape in enumerate(master.shapes):
            if not shape.has_text_frame:
                continue
            for para_idx, para in enumerate(shape.text_frame.paragraphs):
                text = para.text.strip()
                if not text:
                    continue
                pos = f"master.{master_idx}.shape.{shape_idx}.para.{para_idx}"
                seg_id = make_segment_id(text, pos)
                if seg_id in _master_segment_ids:
                    continue  # deduplicate identical text at same position
                _master_segment_ids.add(seg_id)
                segments.append(Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq[0],
                ))
                seq[0] += 1
    return segments
```

**Important:** Master text write-back requires accessing `prs.slide_masters[N].shapes[M].text_frame.paragraphs[K].runs` — same run-merge pattern as DOCX but in PPTX context.

[VERIFIED: Context7 /scanny/python-pptx — slide master placeholder docs]

[ASSUMED] Whether translated master text propagates automatically to layout/slides or requires separate write-back per layout — needs empirical test with a fixture PPTX.

### Q4: Overflow Measurement (PPTX-03, LAYOUT-02, LAYOUT-03)

**python-pptx API for autofit:**
```python
from pptx.enum.text import MSO_AUTO_SIZE

# Read current font size from first run of first paragraph (heuristic)
source_font_size = shape.text_frame.paragraphs[0].runs[0].font.size
# size is in EMUs (1pt = 12700 EMU), or None if inherited

# After writing translated text back:
# Measure shrink: output_chars / input_chars approximation
ratio = len(translated_text) / max(len(source_text), 1)

# D-03-02: apply auto-fit only if shrink would stay ≥ 0.7
if ratio <= 1.0 / 0.7:  # i.e., text expands by at most ~43%
    shape.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    # LAYOUT-03: record auto_size=True in segment details
else:
    # flag overflow — don't apply auto-fit
    pass  # run_post_check creates the overflow SegmentFlag
```

**`text_frame.autofit_text()` internal method:**
Context7 confirms this method exists and returns `_font_scale` (e.g., 55.0 means font scaled to 55% of original). However, `autofit_text()` requires the text to already be in the frame and a working font backend — it does not work reliably in the headless/no-GUI context of the arq worker without PowerPoint installed. [ASSUMED: headless behavior needs empirical test]

**Recommended approach (D-03-02 compliant):**
Use character-count ratio as the shrink proxy. It is conservative and avoids requiring a rendering engine:

```python
# char_ratio > 1 means text expanded (e.g., EN→JA often expands)
char_ratio = len(translated_text) / max(len(source_text), 1)
shrink_factor = 1.0 / char_ratio  # how much font would need to shrink

if shrink_factor >= 0.7:
    # Safe to auto-fit: font won't go below 70% of original size
    shape.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    details = {"auto_adjusted": True, "char_ratio": round(char_ratio, 3)}
else:
    # Would shrink below 0.7 — flag overflow instead
    details = {"auto_adjusted": False, "char_ratio": round(char_ratio, 3)}
    # insert SegmentFlag(flag_type=FlagType.overflow, ...)
```

[VERIFIED: Context7 /scanny/python-pptx — MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE, autofit_text() docs]

### Q5: Speaker Notes Path (PPTX-01)

```python
def extract_notes_segments(slide, slide_idx: int, seq: list[int]) -> list[Segment]:
    if not slide.has_notes_slide:
        return []
    notes_tf = slide.notes_slide.notes_text_frame
    segments = []
    for para_idx, para in enumerate(notes_tf.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        pos = f"slide.{slide_idx}.notes.para.{para_idx}"
        segments.append(Segment.from_text(
            source_text=text,
            structural_position=pos,
            seq_in_job=seq[0],
        ))
        seq[0] += 1
    return segments
```

**Notes reassembler pattern:** Access the same `notes_text_frame` and overwrite paragraph runs using the same run-merge strategy as DOCX — `para.runs[0].text = translated`, `para.runs[1:].text = ""`. [VERIFIED: Context7 /scanny/python-pptx — notes_slide, notes_text_frame docs]

### Q6: Table Cell Traversal (PPTX-01)

```python
def walk_table(table, shape_pos: str, seq: list[int]) -> Iterator[Segment]:
    for row_idx, row in enumerate(table.rows):
        for col_idx, cell in enumerate(row.cells):
            for para_idx, para in enumerate(cell.text_frame.paragraphs):
                text = para.text.strip()
                if not text:
                    continue
                pos = f"{shape_pos}.table.row.{row_idx}.col.{col_idx}.para.{para_idx}"
                yield Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq[0],
                )
                seq[0] += 1
```

**Reassembler:** Locate cell by `(row_idx, col_idx)` parsed from `structural_position`, then apply run-merge write-back on the cell's paragraph runs. [VERIFIED: Context7 /scanny/python-pptx — table XML, cell access docs]

### Q7: Block-Level Extraction + HTML Round-Trip (PDF-01, D-03-06)

**Important clarification on `clip` + `html`:**

From PyMuPDF docs: "`clip` does not affect `html`, `xhtml`, and `xml` output formats." [VERIFIED: Context7 /websites/pymupdf_readthedocs_io_en]

**Correct workflow:**

```python
# Step 1: Get blocks for column clustering + segmentation
page_dict = page.get_text("dict")  # returns {"blocks": [...], "width": ..., "height": ...}
text_blocks = [b for b in page_dict["blocks"] if b["type"] == 0]  # type 0 = text

# Step 2: For each block, get its HTML representation
# Use rawdict with clip to get span-level data, then reconstruct minimal HTML
for block in text_blocks:
    bbox = pymupdf.Rect(block["bbox"])
    # Get structured span data for this block
    block_dict = page.get_text("rawdict", clip=bbox)
    # Convert spans to minimal HTML preserving bold/italic
    html = _spans_to_html(block_dict["blocks"])

# Alternative: get whole-page HTML and carve by bbox
whole_html = page.get_text("html")
# Then filter by block bboxes — but this is fragile; prefer rawdict+clip approach
```

**Recommended:** Use `rawdict` + `clip` per block to extract structured span data, then generate minimal HTML (`<b>`, `<i>`, `<span style="...">`) before handing to the translator.

[VERIFIED: Context7 /websites/pymupdf_readthedocs_io_en — clip parameter docs]

### Q8: HTML Inline Translation Strategy (D-03-06)

**Chosen approach (D-03-06 locked): feed HTML with "preserve tags" system instruction.**

```python
# In translate_batch or a new translate_html variant:
SYSTEM_HTML = (
    "You are a professional translator. "
    "Translate only the visible text content. "
    "Preserve ALL HTML tags exactly as they appear — do not add, remove, or modify any HTML tags. "
    "Only translate the human-readable text between tags."
)
```

**Risk:** qwen-mt-turbo may strip or modify tags. Mitigation:
- Use placeholder protection (CORE-05 pattern): extract text nodes → replace with `⟦T{n}⟧` tokens → translate → restore. Apply this to HTML tags as non-translatable tokens.

**Recommended implementation (safer than raw HTML feed):**

```python
import re

TAG_RE = re.compile(r"<[^>]+>")

def translate_html_segment(html: str) -> str:
    """Replace HTML tags with T-tokens, translate text, restore tags."""
    tags = []
    def replace_tag(m):
        tags.append(m.group(0))
        return f"⟦T{len(tags)-1}⟧"
    text_with_tokens = TAG_RE.sub(replace_tag, html)
    translated = translate(text_with_tokens)  # existing translate_batch
    # Restore tags
    for i, tag in enumerate(tags):
        translated = translated.replace(f"⟦T{i}⟧", tag)
    return translated
```

This reuses the existing CORE-05 placeholder machinery and is the most reliable approach. [ASSUMED: qwen-mt-turbo may handle HTML tags natively — empirical test recommended during Wave 0]

### Q9: `insert_htmlbox` Overflow Detection (PDF-03, LAYOUT-02)

**Return value (VERIFIED):**
`insert_htmlbox` returns a `tuple[float, float]` = `(spare_height, scale)`:
- `spare_height > 0`: text fit, N points remain below last text line
- `spare_height == -1`: fitting **failed** (only happens when `scale_low > 0` prevents further scaling)
- `scale`: scaling factor applied (0 < scale ≤ 1); equals `scale_low` when fitting failed

[VERIFIED: Context7 /pymupdf/pymupdf — insert_htmlbox return value docs]

**Overflow detection pattern:**

```python
# Set scale_low=0.7 to match D-03-02 threshold (don't shrink below 70%)
spare_height, scale = page.insert_htmlbox(
    rect=block_bbox,
    text=translated_html,
    css=noto_css,
    archive=noto_archive,
    scale_low=0.7,  # stop scaling at 70% — return -1 if still overflows
    overlay=True,
)

if spare_height < 0:
    # Overflow: scale hit minimum (scale == 0.7), still didn't fit
    # Insert SegmentFlag(flag_type=FlagType.overflow, ...)
    details = {"scale_applied": scale, "scale_low": 0.7}
elif scale < 1.0:
    # Auto-adjusted: scaled but fit within 0.7 threshold
    # LAYOUT-03: record as auto-adjusted
    details = {"auto_adjusted": True, "scale_applied": round(scale, 3)}
```

**Default behavior (scale_low=0):** Always scales down to fit — no overflow ever returned. You MUST set `scale_low=0.7` to get the `spare_height == -1` signal.

### Q10: Column Clustering Algorithm (PDF-04, D-03-03)

**No ML deps needed.** Simple histogram-based approach:

```python
def cluster_columns(
    text_blocks: list[dict],
    page_width: float,
    gap_threshold: float = 0.30,  # D-03-03: 30% of page width
) -> tuple[list[list[dict]], bool]:
    """
    Returns (column_groups, is_degraded).
    column_groups: list of block lists, one per column (left-to-right)
    is_degraded: True if 3+ columns detected or clustering ambiguous
    """
    if not text_blocks:
        return [text_blocks], False

    # Compute x-midpoints for each block
    midpoints = [(b["bbox"][0] + b["bbox"][2]) / 2 for b in text_blocks]
    min_x = min(midpoints)
    max_x = max(midpoints)

    # Histogram: 20 bins across page width
    bin_count = 20
    bin_width = page_width / bin_count
    histogram = [0] * bin_count
    for mid in midpoints:
        bin_idx = min(int(mid / bin_width), bin_count - 1)
        histogram[bin_idx] += 1

    # Find gaps: bins with zero (or near-zero) density
    gap_min_width = page_width * gap_threshold  # e.g., 30% of 595pt = ~179pt
    gap_min_bins = int(gap_min_width / bin_width)  # ~6 bins

    # Identify runs of zero bins wider than gap_min_bins
    gaps = _find_gaps(histogram, gap_min_bins)

    if len(gaps) == 0:
        return [sorted(text_blocks, key=lambda b: b["bbox"][1])], False  # 1 col
    elif len(gaps) == 1:
        split_x = gaps[0] * bin_width + bin_width / 2
        left = [b for b in text_blocks if (b["bbox"][0] + b["bbox"][2]) / 2 < split_x]
        right = [b for b in text_blocks if (b["bbox"][0] + b["bbox"][2]) / 2 >= split_x]
        # Sort each column top-to-bottom
        left.sort(key=lambda b: b["bbox"][1])
        right.sort(key=lambda b: b["bbox"][1])
        return [left, right], False  # 2-col
    else:
        # 3+ columns or ambiguous — D-03-03: degrade to flat
        flat = sorted(text_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
        return [flat], True  # is_degraded=True → multi_column_degraded flag

def _find_gaps(histogram: list[int], min_width_bins: int) -> list[int]:
    """Return list of bin indices where zero-density runs start, min_width_bins wide."""
    gaps = []
    run_start = None
    for i, count in enumerate(histogram):
        if count == 0:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= min_width_bins:
                gaps.append((run_start + i) // 2)  # midpoint of gap
            run_start = None
    return gaps
```

[ASSUMED: histogram bin count of 20 is adequate for standard A4/Letter pages. Adjust if real PDFs produce noisy splits.]

### Q11: `add_redact_annot` + `apply_redactions` Workflow (PDF-02, D-03-05)

**Exact sequence:**

```python
import pymupdf

doc = pymupdf.open(input_path)
for page in doc:
    text_blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]

    # --- Pass 1: mark all blocks for redaction ---
    for block in text_blocks:
        rect = pymupdf.Rect(block["bbox"])
        # fill=False → transparent fill (preserves background)
        # fill=(1,1,1) → white fill
        page.add_redact_annot(rect, fill=False)

    # --- Pass 2: apply redactions ---
    # images=1 (PDF_REDACT_IMAGE_NONE): do NOT touch images
    # graphics=0 (PDF_REDACT_LINE_ART_NONE): do NOT touch vector graphics
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                          graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)

    # --- Pass 3: insert translated HTML ---
    for block, segment in zip(text_blocks, page_segments):
        translated_html = translated_map.get(segment.id, segment.source_text)
        rect = pymupdf.Rect(block["bbox"])
        spare_height, scale = page.insert_htmlbox(
            rect, translated_html,
            css=noto_css, archive=noto_archive,
            scale_low=0.7,
        )
        if spare_height < 0:
            # flag overflow
            pass

doc.subset_fonts()  # reduce file size
doc.save(output_path, garbage=3, deflate=True)
```

**`PDF_REDACT_IMAGE_NONE` constant:** This is `images=1` numerically. The constant name `PDF_REDACT_IMAGE_NONE` is available in PyMuPDF 1.26+. [VERIFIED: Context7 /pymupdf/pymupdf — apply_redactions parameters]

**Critical ordering:** All `add_redact_annot` calls for a page MUST precede the single `apply_redactions` call for that page. Cannot interleave with `insert_htmlbox`.

### Q12: Noto Font Registration with `insert_htmlbox` (D-03-04)

**Canonical pattern using `Archive` + `@font-face`:**

```python
import pymupdf

# Noto fonts are installed in Docker at /usr/share/fonts/truetype/noto/
NOTO_FONT_DIR = "/usr/share/fonts/truetype/noto"

def build_noto_archive_and_css() -> tuple[pymupdf.Archive, str]:
    arch = pymupdf.Archive(NOTO_FONT_DIR)
    css = """
    @font-face {
        font-family: noto;
        src: url(NotoSans-Regular.ttf);
    }
    @font-face {
        font-family: noto;
        src: url(NotoSans-Bold.ttf);
        font-weight: bold;
    }
    @font-face {
        font-family: noto;
        src: url(NotoSans-Italic.ttf);
        font-style: italic;
    }
    @font-face {
        font-family: noto-cjk;
        src: url(NotoSansCJK-Regular.ttc);
    }
    * {
        font-family: noto, noto-cjk, sans-serif;
        font-size: 10pt;
    }
    """
    return arch, css
```

**Note:** `insert_htmlbox`'s CSS engine uses HarfBuzz for complex script shaping (verified in PyMuPDF docs) — handles Vietnamese diacritics and CJK without additional configuration. [VERIFIED: Context7 /websites/pymupdf_readthedocs_io_en — insert_htmlbox description]

[ASSUMED: Exact Noto font filenames under `fonts-noto-cjk` apt package vary by Debian version. Verify at docker build time with `fc-list | grep Noto`.]

### Q13: HTML Translation API Contract

**Decision:** No new `translate_html()` function needed. Extend the existing pipeline using the placeholder-protection approach from Q8.

**Implementation location:** `pipeline/pdf/extractor.py` — a module-level helper `spans_to_html(block_dict)` converts span data to minimal HTML before handing to the standard `translate_batch()`. The translator (`llm/translator.py`) remains unchanged.

```python
# pipeline/pdf/extractor.py
def spans_to_html(block: dict) -> str:
    """Convert a get_text("rawdict") block to minimal HTML preserving bold/italic."""
    parts = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            flags = span.get("flags", 0)
            is_bold = bool(flags & 2**4)
            is_italic = bool(flags & 2**1)
            if is_bold and is_italic:
                parts.append(f"<b><i>{text}</i></b>")
            elif is_bold:
                parts.append(f"<b>{text}</b>")
            elif is_italic:
                parts.append(f"<i>{text}</i>")
            else:
                parts.append(text)
        parts.append(" ")  # line separator
    return "".join(parts).strip()
```

### Q14: Worker Dispatch Pattern

**Current:** `_run_translation()` hardcodes `Document(job.input_path)` (DOCX). Must dispatch by `job.input_format`.

**Recommended: match/case in `_run_translation()`** — no Protocol abstraction needed for PoC.

```python
async def _run_translation(ctx, session, job_id: str) -> None:
    job = await get_job(session, job_id)
    ...
    match job.input_format:
        case "docx":
            from app.pipeline.docx.extractor import extract_run_segments
            from app.pipeline.docx.reassembler import reassemble_docx_runs
            doc = Document(job.input_path)
            if job.has_tracked_changes and job.tracked_changes_action == "strip":
                doc = strip_tracked_changes(doc)
            segments = extract_run_segments(doc, job_id)
            ...
            output_doc = reassemble_docx_runs(doc, segments, translated_map)
            output_path = _save_docx(output_doc, job_id, data_dir)

        case "pptx":
            from app.pipeline.pptx.extractor import extract_pptx_segments
            from app.pipeline.pptx.reassembler import reassemble_pptx
            from pptx import Presentation
            prs = Presentation(job.input_path)
            segments = extract_pptx_segments(prs, job_id)
            ...
            output_prs = reassemble_pptx(prs, segments, translated_map)
            output_path = _save_pptx(output_prs, job_id, data_dir)

        case "pdf":
            from app.pipeline.pdf.extractor import extract_pdf_segments
            from app.pipeline.pdf.reassembler import reassemble_pdf
            import pymupdf
            doc = pymupdf.open(job.input_path)
            segments, smartart_flags = extract_pdf_segments(doc, job_id)
            ...
            reassemble_pdf(doc, segments, translated_map, output_path)

        case _:
            raise ValueError(f"Unsupported format: {job.input_format}")
```

### Q15: `structural_position` Schema Convention

Full convention table for all formats:

| Format | Content Type | Example structural_position |
|--------|-------------|----------------------------|
| DOCX | body paragraph | `para.3` |
| DOCX | table cell | `cell_para.5.run2` |
| DOCX | header | `header.0` |
| PPTX | text box body | `slide.3.shape.1.tf.0.para.2` |
| PPTX | notes | `slide.3.notes.para.1` |
| PPTX | table cell | `slide.3.shape.1.table.row.0.col.1.para.0` |
| PPTX | nested group | `slide.3.shape.2.group.shape.0.tf.0.para.1` |
| PPTX | SmartArt | `slide.3.shape.4.smartart` |
| PPTX | master | `master.0.shape.2.para.0` |
| PDF (2-col) | block in col 0 | `page.2.col.0.block.5` |
| PDF (2-col) | block in col 1 | `page.2.col.1.block.2` |
| PDF (degraded) | flat block | `page.2.block.7` |

**`formatBreadcrumb()` detection prefix table (confirmed by 03-UI-SPEC.md):**

| Prefix | Format |
|--------|--------|
| `slide.` | PPTX |
| `page.` | PDF |
| `master.` | PPTX master (treat as PPTX) |
| anything else | DOCX |

### Q16: Test Fixtures for Golden-Path Validation

**PPTX test fixtures (generate programmatically with python-pptx — no binary blobs):**

```python
# tests/pipeline/test_pptx_extractor.py
from pptx import Presentation
from pptx.util import Inches, Pt

@pytest.fixture
def simple_pptx(tmp_path):
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    # Text box
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "Hello world"
    # Speaker notes
    notes = slide.notes_slide.notes_text_frame
    notes.text = "Speaker note text"
    # Table
    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1.5))
    table = table_shape.table
    table.cell(0, 0).text = "Cell A"
    table.cell(0, 1).text = "Cell B"
    path = tmp_path / "simple.pptx"
    prs.save(str(path))
    return path
```

Fixtures needed:
- `simple_pptx`: text box + notes + table (PPTX-01)
- `group_pptx`: nested group with 2 levels (PPTX-04)
- `smartart_pptx`: slide with SmartArt (requires inserting `p:grpSp` with SmartArt XML, or use a real PPTX file from Microsoft samples)
- `overflow_pptx`: tight text box with long text (PPTX-03)

**PDF test fixtures (generate with PyMuPDF or use public domain PDFs):**

```python
@pytest.fixture
def single_col_pdf(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF world")
    path = tmp_path / "single.pdf"
    doc.save(str(path))
    return path
```

For 2-column PDF: use a real academic PDF from arXiv (CC-BY license). Recommended source: [arXiv.org](https://arxiv.org) — any 2-column CS paper. Store in `tests/fixtures/` as a tracked binary (small PDFs are < 100KB typically).

For SmartArt PPTX: Microsoft provides sample files at [https://docs.microsoft.com/en-us/openxml/](https://docs.microsoft.com/en-us/openxml/) — check license. Alternative: generate via LibreOffice scripting.

### Q17: Validation Architecture (Nyquist)

See `## Validation Architecture` section below.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text insertion with font embedding | Custom ReportLab renderer | `PyMuPDF insert_htmlbox` + Noto Archive | HarfBuzz shaping, auto line-wrap, CJK, RTL all built in |
| PPTX shape-type detection | Custom XML parsing for shape classification | `shape.shape_type` enum + `shape.has_text_frame` | python-pptx wraps OOXML spec correctly |
| PDF image preservation through redaction | Custom image copy loop | `apply_redactions(images=PDF_REDACT_IMAGE_NONE)` | Builtin flag; custom code is error-prone with image xrefs |
| Font CSS for insert_htmlbox | Font registration from scratch | `pymupdf.Archive(dir)` + `@font-face` CSS | Archive handles font discovery; HarfBuzz shaping is automatic |
| Column reading order sort | ML-based layout analysis | Histogram gap detection on x-midpoints | PyMuPDF docs confirm this is the community standard approach |
| PPTX auto-fit | Manual font-size binary search | `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` | python-pptx sets the OOXML auto-fit attribute that PowerPoint respects |

---

## Common Pitfalls

### Pitfall 1: `paragraph.text = value` Destroys PPTX Formatting
**What goes wrong:** Same as DOCX — `paragraph.text = value` calls `paragraph.clear()` removing all run formatting.
**How to avoid:** Same run-merge strategy: `para.runs[0].text = translated`, `para.runs[1:].text = ""`
**Warning signs:** Translated PPTX loses bold/italic/color on all text.

### Pitfall 2: `insert_htmlbox` Default `scale_low=0` Never Reports Overflow
**What goes wrong:** With `scale_low=0` (default), `insert_htmlbox` always scales down to fit and returns `spare_height >= 0`. You never detect overflow.
**How to avoid:** Always pass `scale_low=0.7` for Phase 3's overflow detection.
**Warning signs:** All segments have `spare_height > 0` even on obviously long translated text.

### Pitfall 3: `apply_redactions` Order
**What goes wrong:** Calling `insert_htmlbox` before `apply_redactions` on the same page — the redaction removes the newly inserted text.
**How to avoid:** For each page: all `add_redact_annot` → `apply_redactions` → all `insert_htmlbox`. Never interleave.
**Warning signs:** PDF output has blank pages or missing text.

### Pitfall 4: `clip` Parameter Ignored for `html` Format
**What goes wrong:** `page.get_text("html", clip=bbox)` silently returns whole-page HTML, ignoring clip.
**How to avoid:** Use `page.get_text("rawdict", clip=bbox)` for structured per-block data. Use `page.get_text("html")` only for whole-page HTML if needed.
**Warning signs:** Block segmentation is wildly off — all text on page in every "block".

### Pitfall 5: SmartArt `has_text_frame` is False
**What goes wrong:** Checking `shape.has_text_frame` on SmartArt shapes returns False, so they are silently skipped.
**How to avoid:** Check `is_smartart(shape)` BEFORE `shape.has_text_frame`. See Q2 for detection order.
**Warning signs:** PPTX-02 UAT fails — SmartArt shapes produce no segment rows in review UI.

### Pitfall 6: PDF `type` Field on Blocks
**What goes wrong:** `page.get_text("dict")["blocks"]` returns both text blocks (`type==0`) and image blocks (`type==1`). Image blocks have no `"lines"` key — iterating `block["lines"]` raises KeyError.
**How to avoid:** `text_blocks = [b for b in blocks if b["type"] == 0]`
**Warning signs:** Worker crashes with KeyError on image-heavy PDFs.

### Pitfall 7: `python-pptx 1.0.x` Breaking Changes from 0.6.x
**What goes wrong:** If someone downgrades to 0.6.x (e.g., via a conflicting package), several APIs changed in 1.0.x.
**How to avoid:** Pin `python-pptx==1.0.2` exactly in pyproject.toml.

### Pitfall 8: Noto Font Path Varies by OS/Docker Base
**What goes wrong:** Font path `/usr/share/fonts/truetype/noto/` is Debian/Ubuntu specific. Different distros place fonts elsewhere.
**How to avoid:** Use `fc-list | grep Noto` in Docker to discover actual path; or use Python `fonttools`/`fc-match` to resolve. Or hardcode the apt-installed path and document it.

---

## Code Examples

### PPTX: Minimal Extractor Shell

```python
# pipeline/pptx/extractor.py
from pptx import Presentation
from app.pipeline.segment import Segment

def extract_pptx_segments(prs: Presentation, job_id: str) -> list[Segment]:
    segments: list[Segment] = []
    seq = [0]  # mutable counter

    # Master slides first (deduplicated)
    segments.extend(extract_master_segments(prs, seq))

    for slide_idx, slide in enumerate(prs.slides):
        # Body shapes
        list(walk_shape_tree(slide.shapes, slide_idx, seq, f"slide.{slide_idx}"))
        segments.extend(...)

        # Speaker notes
        segments.extend(extract_notes_segments(slide, slide_idx, seq))

    return segments
```

### PPTX: Reassembler Shell

```python
# pipeline/pptx/reassembler.py
from pptx import Presentation

def reassemble_pptx(
    prs: Presentation,
    segments: list[Segment],
    translated_map: dict[str, str],
) -> Presentation:
    seg_by_pos = {s.structural_position: s for s in segments}

    for slide_idx, slide in enumerate(prs.slides):
        _write_back_shapes(slide.shapes, translated_map, seg_by_pos, f"slide.{slide_idx}")

    return prs  # mutated in-place (return for symmetry with DOCX pattern)
```

### PDF: Minimal Extractor Shell

```python
# pipeline/pdf/extractor.py
import pymupdf
from app.pipeline.pdf.columns import cluster_columns
from app.pipeline.segment import Segment

def extract_pdf_segments(doc: pymupdf.Document, job_id: str) -> list[Segment]:
    segments: list[Segment] = []
    seq = [0]

    for page_num, page in enumerate(doc):
        blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
        column_groups, is_degraded = cluster_columns(blocks, page.rect.width)

        for col_idx, col_blocks in enumerate(column_groups):
            for block_idx, block in enumerate(col_blocks):
                # Extract structured spans → minimal HTML
                raw_dict = page.get_text("rawdict", clip=pymupdf.Rect(block["bbox"]))
                html = spans_to_html(raw_dict["blocks"][0] if raw_dict["blocks"] else {})
                if not html.strip():
                    continue

                if is_degraded:
                    pos = f"page.{page_num}.block.{block_idx}"
                else:
                    pos = f"page.{page_num}.col.{col_idx}.block.{block_idx}"

                segments.append(Segment.from_text(
                    source_text=html,
                    structural_position=pos,
                    seq_in_job=seq[0],
                ))
                seq[0] += 1

    return segments
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `paragraph.text = value` (PPTX) | Run-merge write-back | python-pptx design (always wrong) | Formatting preservation |
| `PDF_REDACT_IMAGE_PIXELS` (default) | `PDF_REDACT_IMAGE_NONE` for translation | PyMuPDF 1.16+ | Images preserved through redaction |
| `insert_textbox` for PDF reinsertion | `insert_htmlbox` with Story engine | PyMuPDF 1.21+ | Bold/italic/CJK/RTL all work |
| Per-span bbox-pin for PDF translation | Block-level HTML round-trip | D-03-06 (project decision) | Handles text expansion correctly |

**Deprecated / avoid:**
- `page.get_text("words")` — no structural info; use `"dict"` or `"rawdict"`
- `text_frame.autofit_text()` — requires rendering engine; may fail headless; use `MSO_AUTO_SIZE` attribute directly

---

## Runtime State Inventory

This is a greenfield phase adding new code paths only — no rename, refactor, or migration. No runtime state audit required.

**Stored data:** None — no existing PPTX/PDF job records in DB (Phase 3 is new capability)
**Live service config:** None — no n8n/external services reference PPTX/PDF format strings
**OS-registered state:** None
**Secrets/env vars:** No new secrets needed; existing DASHSCOPE_API_KEY covers all formats
**Build artifacts:** `python-pptx==1.0.2` and `pymupdf>=1.26` are new deps — Docker image rebuild required after adding to pyproject.toml

---

## Validation Architecture

nyquist_validation: `true` (absent = enabled per config.json)

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8+ + pytest-asyncio |
| Config file | `backend/pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `cd backend && uv run pytest tests/pipeline/ -x -q` |
| Full suite command | `cd backend && uv run pytest --cov=src/app --cov-fail-under=80 -q` |
| Frontend test command | `cd frontend && npm run test` (vitest) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PPTX-01 | text box + notes + table + master extracted + reassembled | unit | `pytest tests/pipeline/test_pptx_extractor.py -x` | ❌ Wave 0 |
| PPTX-02 | SmartArt shapes produce `smartart` flag, not silently skipped | unit | `pytest tests/pipeline/test_pptx_extractor.py::test_smartart_flagged -x` | ❌ Wave 0 |
| PPTX-03 | overflow detection sets flag; auto-fit applies when shrink ≥ 0.7 | unit | `pytest tests/pipeline/test_pptx_reassembler.py::test_overflow -x` | ❌ Wave 0 |
| PPTX-04 | nested group walker finds text at all nesting levels | unit | `pytest tests/pipeline/test_pptx_extractor.py::test_group_recursion -x` | ❌ Wave 0 |
| PDF-01 | PDF parsed; segments have bbox, font, size, source_text | unit | `pytest tests/pipeline/test_pdf_extractor.py -x` | ❌ Wave 0 |
| PDF-02 | redact-reinsert produces PDF with Noto text | unit | `pytest tests/pipeline/test_pdf_reassembler.py::test_round_trip -x` | ❌ Wave 0 |
| PDF-03 | overflow flagged when scale < 0.7 | unit | `pytest tests/pipeline/test_pdf_reassembler.py::test_overflow_flag -x` | ❌ Wave 0 |
| PDF-04 | 2-col PDF produces 2 column groups in reading order | unit | `pytest tests/pipeline/test_pdf_columns.py -x` | ❌ Wave 0 |
| LAYOUT-02 | overflow SegmentFlag present in DB for flagged segments | integration | `pytest tests/pipeline/test_pdf_reassembler.py::test_overflow_db_flag -x` | ❌ Wave 0 |
| LAYOUT-03 | auto-adjusted metadata in SegmentFlag details | unit | `pytest tests/pipeline/test_pptx_reassembler.py::test_auto_adjusted -x` | ❌ Wave 0 |
| Frontend: FlagBadge | smartart + multi_column_degraded badges render correctly | unit (vitest) | `npm run test -- FlagBadge` | ❌ Wave 0 |
| Frontend: formatBreadcrumb | all position formats parsed correctly | unit (vitest) | `npm run test -- formatBreadcrumb` | ❌ Wave 0 |

### Property Tests (round-trip invariants)

```python
# Invariant 1: segment count preserved through reassembly
assert len(extracted_segments) == len(translated_map)  # existing CORE-03

# Invariant 2: non-text content preserved (images, vector graphics)
# For PDF: image blocks count before == after
before_images = len([b for b in page.get_text("dict")["blocks"] if b["type"] == 1])
# ... after reassembly ...
after_images = len([b for b in new_page.get_text("dict")["blocks"] if b["type"] == 1])
assert before_images == after_images

# Invariant 3: SmartArt segments produce no reassembly output
# (write-back is skipped for smartart positions)

# Invariant 4: structural_position uniqueness per job
positions = [s.structural_position for s in segments]
assert len(positions) == len(set(positions))
```

### Adversarial Tests

| Scenario | Test | Expected Behavior |
|----------|------|-------------------|
| Malformed PPTX (corrupted XML) | `pytest tests/pipeline/test_pptx_extractor.py::test_malformed` | Worker logs error, job → `failed`, no crash |
| Encrypted PDF (password-protected) | `pytest tests/pipeline/test_pdf_extractor.py::test_encrypted` | `pymupdf.open()` raises, caught, job → `failed` |
| Empty PPTX (no slides) | `test_empty_pptx` | Returns `[]` segments, job → `done` with empty output |
| PPTX with zero-run text frames | `test_zero_run_tf` | Falls back to `text_frame.text` para extraction |
| PDF with 3 columns | `test_three_col_pdf` | `multi_column_degraded` flag set, flat reading order |
| All-image PDF (no text layer) | `test_image_pdf` | Returns `[]` segments, job → `done` (Phase 4 handles) |
| Very long translated text (> 5x expansion) | `test_extreme_expansion` | `overflow` flag set, `spare_height == -1` |

### Observability (logs/metrics for post-hoc debugging)

Per-job structured log fields to emit (via structlog):
```python
log.info("pptx_extracted",
    job_id=job_id,
    slide_count=len(prs.slides),
    segment_count=len(segments),
    smartart_count=smartart_shapes_found,
)
log.info("pdf_extracted",
    job_id=job_id,
    page_count=len(doc),
    segment_count=len(segments),
    degraded_pages=degraded_count,
)
log.info("pdf_block_overflow",
    job_id=job_id,
    page=page_num,
    block=block_idx,
    scale_applied=scale,
)
```

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest tests/pipeline/ -x -q`
- **Per wave merge:** `cd backend && uv run pytest --cov=src/app --cov-fail-under=80 -q && cd ../frontend && npm run test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps (files that must be created before implementation)
- [ ] `backend/tests/pipeline/test_pptx_extractor.py` — covers PPTX-01..04
- [ ] `backend/tests/pipeline/test_pptx_reassembler.py` — covers PPTX-03, LAYOUT-03
- [ ] `backend/tests/pipeline/test_pdf_extractor.py` — covers PDF-01
- [ ] `backend/tests/pipeline/test_pdf_reassembler.py` — covers PDF-02, PDF-03, LAYOUT-02
- [ ] `backend/tests/pipeline/test_pdf_columns.py` — covers PDF-04
- [ ] `frontend/src/__tests__/formatBreadcrumb.test.ts` — covers D-03-07 breadcrumb
- [ ] `frontend/src/__tests__/FlagBadge.test.tsx` — extend existing file with smartart + multi_column_degraded
- [ ] `backend/tests/fixtures/` — 2-column PDF fixture (binary, track in git)

---

## Security Domain

No new authentication, session, or access-control surfaces introduced. Phase 3 is file processing only.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | MIME type check on upload (existing UPLD-02); PPTX/PDF extension whitelist in UploadForm |
| V6 Cryptography | no | No new crypto surfaces |
| File path traversal | yes | Existing `job_id`-scoped paths: `data/jobs/{job_id}/source.{ext}` |
| Malformed input | yes | `pymupdf.open()` + `Presentation()` can raise on corrupt files — all must be caught in `_run_translation`'s outer except |

**Threat specific to Phase 3:** Malicious PDF with crafted bboxes or font references could cause `insert_htmlbox` to fail or produce garbage. Mitigation: the outer try/except in the worker marks job as `failed` rather than crashing the worker process.

---

## Open Questions

1. **Master text write-back propagation**
   - What we know: `prs.slide_master.shapes[N].text_frame` is writable
   - What's unclear: Does editing master text propagate automatically to layout slides, or must each layout's shape be edited independently?
   - Recommendation: Write a fixture test during Wave 0 — edit master text, save, reopen, confirm slides reflect change

2. **qwen-mt-turbo + HTML tag preservation**
   - What we know: qwen-mt-turbo handles `terminology` injection; unclear if it honors HTML tags
   - What's unclear: Will it strip `<b>`, `<i>` tags or hallucinate extra HTML?
   - Recommendation: Test empirically in Wave 0 with a simple `<b>hello</b> world` payload; implement placeholder-protection fallback if tags are corrupted

3. **`autofit_text()` headless reliability**
   - What we know: `text_frame.autofit_text()` calls an internal font scaling calculation
   - What's unclear: Whether this requires a rendering context unavailable in a headless Python process
   - Recommendation: Use char-count ratio (Q4) as primary; `auto_size = TEXT_TO_FIT_SHAPE` as the declarative fallback PowerPoint will apply on open

4. **Noto font filenames on runtime Docker image**
   - What we know: `apt-get install fonts-noto-cjk fonts-noto` installs them; path is `/usr/share/fonts/truetype/noto/`
   - What's unclear: Exact filenames (especially `NotoSansCJK-Regular.ttc` vs `NotoSansCJKsc-Regular.otf`)
   - Recommendation: Add a Wave 0 task: `docker run --rm <image> fc-list | grep Noto` → hardcode discovered paths in `fonts.py`

5. **3+ column PDF triggering multi_column_degraded**
   - What we know: histogram gap algorithm will produce 2+ gaps for 3+ columns
   - What's unclear: Will some 2-column PDFs with uneven column widths produce 2 gaps and trigger false `multi_column_degraded`?
   - Recommendation: Test with arXiv 2-column PDF. If false positives occur, raise `gap_min_bins` or apply a "gap must be in middle 60% of page width" filter.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | ✓ | 3.12 (project requirement) | — |
| `pymupdf` | PDF pipeline | ✗ (not in pyproject.toml) | 1.27.2.3 latest | — (must add) |
| `python-pptx` | PPTX pipeline | ✗ (not in pyproject.toml) | 1.0.2 (pinned) | — (must add) |
| `fonts-noto-cjk` apt pkg | PDF font embedding | ✓ in Docker (CLAUDE.md Dockerfile) | — | fonts-noto as Latin-only fallback |
| `fonts-noto` apt pkg | PDF font embedding | ✓ in Docker | — | — |
| pytest + pytest-asyncio | Backend tests | ✓ | existing | — |
| vitest | Frontend tests | ✓ | existing | — |

**Missing dependencies with no fallback:**
- `pymupdf` — must be added to `backend/pyproject.toml` before any PDF code runs
- `python-pptx` — must be added to `backend/pyproject.toml` before any PPTX code runs

**Note:** Both are listed in CLAUDE.md tech stack but are absent from the current `pyproject.toml`. The first Wave 0 task must add these dependencies.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Master text edits propagate automatically to layout slides | Q3, Open Questions #1 | Master text not translated in output — need per-layout write-back too |
| A2 | `text_frame.autofit_text()` fails headless in arq worker | Q4 | Overhead: if it works, it's more accurate than char-count ratio |
| A3 | Noto font files at `/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf` | Q12 | `insert_htmlbox` falls back to built-in fonts, CJK text garbled |
| A4 | qwen-mt-turbo corrupts HTML tags if fed directly | Q8 | Could simplify to direct HTML feed; placeholder protection adds overhead |
| A5 | Histogram bin count of 20 is adequate for column clustering | Q10 | False positives on 2-col PDFs with uneven column widths |
| A6 | `clip` ignores for `html` format is confirmed behavior (not a version bug) | Q7 | Would change the PDF block HTML extraction strategy |

---

## Sources

### Primary (HIGH confidence)
- [Context7 /scanny/python-pptx] — `MSO_SHAPE_TYPE.IGX_GRAPHIC`, `MSO_SHAPE_TYPE.GROUP`, `GroupShape.shapes`, `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`, `notes_slide.notes_text_frame`, `has_notes_slide`, table cell traversal, graphicFrame/graphicData URI structure
- [Context7 /pymupdf/pymupdf] — `insert_htmlbox(rect, text, scale_low, archive, css)` return value `(spare_height, scale)`, `add_redact_annot`, `apply_redactions(images=PDF_REDACT_IMAGE_NONE)`, `PDF_REDACT_IMAGE_NONE` constant
- [Context7 /websites/pymupdf_readthedocs_io_en] — `page.get_text("dict")["blocks"]`, `clip` parameter behavior for `html` format, `insert_htmlbox` overflow handling, Noto font CSS pattern via `Archive` + `@font-face`
- [Context7 /websites/python-pptx_readthedocs_io_en] — `autofit_text()`, `auto_size` property, speaker notes access pattern

### Secondary (MEDIUM confidence)
- [PyPI pymupdf](https://pypi.org/project/pymupdf/) — latest version 1.27.2.3 verified 2026-04-25
- [PyPI python-pptx](https://pypi.org/project/python-pptx/) — latest version 1.0.2 verified 2026-04-25
- [pymupdf.readthedocs.io — FAQ: multi-column](https://pymupdf.readthedocs.io/en/latest/faq/index.html) — "For multi-column layouts, this helps but isn't perfect. You may need to identify column boundaries yourself using block bounding boxes"

### Tertiary (LOW confidence — verify before relying)
- A1, A2, A4, A5, A6 in Assumptions Log above

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified from PyPI
- PPTX architecture: HIGH — python-pptx APIs verified via Context7
- PDF architecture: HIGH — PyMuPDF APIs verified via Context7; `insert_htmlbox` return value verified
- Column clustering: MEDIUM — algorithm pattern verified, specific bin count is assumed
- HTML translation: MEDIUM — approach chosen, LLM behavior empirically unverified

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (stable libraries; PyMuPDF does minor releases frequently but API is stable)
