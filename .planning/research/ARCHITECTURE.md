# Architecture Research

**Domain:** AI document translation web application (PoC)
**Researched:** 2026-04-17
**Confidence:** HIGH (core pipeline), MEDIUM (OCR subsystem, PDF reassembly)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        BROWSER (Next.js)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Upload +    │  │  Job list /  │  │  Side-by-side segment    │ │
│  │ Lang select │  │  History     │  │  review editor           │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────┬─────────────┘ │
│         │                │                        │               │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌────────────┴─────────────┐ │
│  │  Glossary   │  │   Download   │  │  Job-progress poller     │ │
│  │  manager    │  │   page       │  │  (REST polling / SSE)    │ │
│  └─────────────┘  └──────────────┘  └──────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP/REST
┌──────────────────────────────▼───────────────────────────────────┐
│                      FastAPI REST API                            │
│  POST /jobs          GET /jobs/{id}        GET /jobs/{id}/segs   │
│  POST /glossaries    PATCH /glossaries     GET /glossaries       │
│  PATCH /jobs/{id}/segs/{seg_id}            POST /jobs/{id}/export│
└──────────────────────────────┬───────────────────────────────────┘
                               │  enqueue / read
┌──────────────────────────────▼───────────────────────────────────┐
│                        Redis (ARQ queue)                         │
└──────────────────────────────┬───────────────────────────────────┘
                               │  dequeue
┌──────────────────────────────▼───────────────────────────────────┐
│                    ARQ Background Worker                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                  Translation Pipeline                    │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │    │
│  │  │ Format   │  │  Parser  │  │ Segment  │  │Pre-proc │  │    │
│  │  │ Detector │→ │ (per fmt)│→ │ Extractor│→ │+ Gloss. │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └────┬────┘  │    │
│  │                                                  │        │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │        │    │
│  │  │ Re-      │  │Post-proc │  │Qwen-MT   │◄──────┘        │    │
│  │  │ assembler│◄ │+ verify  │◄ │ client   │                │    │
│  │  └────┬─────┘  └──────────┘  └──────────┘                │    │
│  │       │                                                   │    │
│  │  ┌────▼──────────────────────────────────────────────┐   │    │
│  │  │  OCR subsystem (scanned PDF path only)            │   │    │
│  │  │  PaddleOCR / PP-StructureV3                       │   │    │
│  │  └───────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               │ read / write
┌──────────────────────────────▼───────────────────────────────────┐
│                         Storage Layer                            │
│  ┌──────────────┐  ┌────────────────────┐  ┌──────────────────┐  │
│  │  Local /     │  │  SQLite (PoC) /    │  │  Local /         │  │
│  │  S3 uploads  │  │  Postgres          │  │  S3 outputs      │  │
│  │  (raw files) │  │  (jobs, segments,  │  │  (translated     │  │
│  └──────────────┘  │   glossaries)      │  │   files)         │  │
│                    └────────────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│               External: Qwen-MT (DashScope API)                  │
│  qwen-mt-plus | qwen-mt-flash — 8,192 token limit per request    │
└──────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| Next.js frontend | Upload UI, job history, segment review editor, glossary manager, download | Next.js App Router, React Server + Client Components |
| FastAPI REST API | HTTP boundary: validate input, enqueue jobs, serve segment/glossary CRUD, stream progress | FastAPI with Pydantic models, SQLAlchemy async |
| ARQ Worker | Dequeues jobs, runs the translation pipeline end-to-end, writes progress back to DB | arq + asyncio, one worker process per PoC |
| Format detector | Identify file type from bytes (magic number + extension) | python-magic + extension fallback |
| Parser (per format) | Extract raw document object model from file | python-docx (DOCX), python-pptx (PPTX), PyMuPDF (native PDF), PaddleOCR PP-StructureV3 (scanned PDF) |
| Segment extractor | Produce ordered `Segment` list with id, source text, style context, position metadata | Per-format extractors, shared Segment dataclass |
| Pre-processor | Tag glossary terms, replace non-translatable tokens with opaque placeholders | Regex + trie over glossary terms |
| Qwen-MT client | Batch segments into requests respecting 8 K token limit, call API, retry on 429 | httpx.AsyncClient, exponential back-off |
| Post-processor | Restore placeholders, verify glossary term coverage, length-flag overflow | String replacement + ratio check |
| Reassembler (per format) | Write translated text back into original document structure | python-docx write-in-place (DOCX), python-pptx run replacement (PPTX), PyMuPDF insert_htmlbox (PDF), bilingual-text (scanned PDF) |
| OCR subsystem | Page image → structured text + bounding boxes with confidence scores | PaddleOCR PP-StructureV3 |
| Redis | Job queue broker, job-state store (ARQ uses Redis natively for both) | Redis 7 |
| SQLite / Postgres | Persistent store for jobs, segments (with edits), glossaries | SQLAlchemy async; SQLite is sufficient for PoC |
| Local file storage | Uploaded files, translated output files | Volume-mounted path; swap to S3 post-PoC |

---

## Recommended Project Structure

```
ai-translation/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI routers (one per resource)
│   │   │   ├── jobs.py
│   │   │   ├── segments.py
│   │   │   ├── glossaries.py
│   │   │   └── export.py
│   │   ├── core/              # Settings, lifespan, DB engine
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── job.py
│   │   │   ├── segment.py
│   │   │   └── glossary.py
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── pipeline/          # Translation pipeline (pure functions)
│   │   │   ├── detector.py
│   │   │   ├── segment.py     # Segment dataclass + extractor protocol
│   │   │   ├── parsers/
│   │   │   │   ├── docx.py
│   │   │   │   ├── pptx.py
│   │   │   │   ├── pdf_native.py
│   │   │   │   └── pdf_scanned.py
│   │   │   ├── preprocessor.py
│   │   │   ├── qwen_client.py
│   │   │   ├── postprocessor.py
│   │   │   └── reassemblers/
│   │   │       ├── docx.py
│   │   │       ├── pptx.py
│   │   │       ├── pdf_native.py
│   │   │       └── pdf_scanned.py
│   │   ├── ocr/               # OCR wrapper (only called by pdf_scanned)
│   │   │   └── paddleocr.py
│   │   └── worker.py          # ARQ WorkerSettings + job function
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── (upload)/          # Upload + language picker
│   │   ├── jobs/[id]/         # Job status + review editor
│   │   ├── jobs/[id]/export/  # Download page
│   │   └── glossaries/        # Glossary CRUD
│   ├── components/
│   │   ├── SegmentTable.tsx    # Side-by-side review rows
│   │   ├── UploadDropzone.tsx
│   │   └── GlossaryForm.tsx
│   └── package.json
├── docker-compose.yml
└── .planning/
```

### Structure Rationale

- **pipeline/**: All translation logic is pure functions that take and return data structures — no FastAPI dependencies, fully testable in isolation.
- **parsers/ and reassemblers/**: Symmetric per-format directories so adding a new format is a self-contained addition.
- **worker.py**: Single entry-point for ARQ; imports pipeline functions. Keeps HTTP and queue concerns separate.
- **ocr/**: Isolated so the OCR model can be swapped (Tesseract, Azure DI) without touching the pipeline.

---

## Architectural Patterns

### Pattern 1: Segment-Centric Data Model

**What:** Every piece of translatable text is represented as a `Segment` record from parse-time forward. All pipeline stages (pre-process, translate, post-process) operate on `list[Segment]`. Reassemblers read segments by their position metadata, not by text content.

**When to use:** Always — this is the backbone of the system.

**Trade-offs:** Adds a serialisation layer; gains reliable round-tripping between segment edits and reassembly.

```python
@dataclass(frozen=True)
class Segment:
    id: str                    # UUID, stable across the job
    source_text: str           # Original text (never mutated)
    position: dict             # Format-specific: {"para_idx": 3, "run_idx": 1} for DOCX
    style_context: dict        # Font size, bold, etc. — for overflow detection
    order: int                 # Reading order (for reassembler)
```

The DB stores `source_text`, `translated_text` (nullable until done), `edited_text` (nullable, set by reviewer), and `overflow_flag` (bool). On export, reassemblers use `edited_text ?? translated_text`.

### Pattern 2: Placeholder Token Protection

**What:** Before sending text to Qwen, the pre-processor scans for non-translatable tokens (URLs, file paths, variable names like `{{name}}`, numeric IDs, inline code) and replaces them with opaque markers `⟦T1⟧`, `⟦T2⟧`, etc. The post-processor restores them after translation.

**When to use:** Every Qwen call, for every format.

**Trade-offs:** Opaque markers can confuse the model if they appear mid-sentence; keep markers short and distinct. Risk: model outputs marker in wrong position — post-processor must detect and flag.

```python
import re

NON_TRANSLATABLE = re.compile(
    r'(https?://\S+|{{[^}]+}}|\b[A-Z_]{3,}\b|\d{5,})'
)

def protect(text: str) -> tuple[str, dict[str, str]]:
    tokens: dict[str, str] = {}
    def replace(m: re.Match) -> str:
        key = f"⟦T{len(tokens)+1}⟧"
        tokens[key] = m.group(0)
        return key
    protected = NON_TRANSLATABLE.sub(replace, text)
    return protected, tokens

def restore(text: str, tokens: dict[str, str]) -> str:
    for key, val in tokens.items():
        text = text.replace(key, val)
    return text
```

### Pattern 3: Adaptive Batching to Qwen-MT

**What:** Segments are grouped into batches where total token count stays under 7,000 (leaving 1,192 token headroom for the glossary `terms` payload and system overhead). Each batch is a single Qwen-MT API call using the `terms` parameter for glossary injection.

**When to use:** Always — never send one segment per call (wastes API calls and per-request latency) and never send the whole document (exceeds 8,192 token limit).

**Trade-offs:** Batching slightly dilutes per-segment context, but Qwen-MT is trained for segmented input. Batching N=10–20 paragraphs is the sweet spot for DOCX; use smaller batches (N=3–5) for PPTX to keep layout units together.

```python
# Pseudo-code — rough token estimate (1 token ≈ 4 chars for CJK-heavy text)
def batch_segments(segments: list[Segment], max_tokens: int = 7000) -> list[list[Segment]]:
    batches, current, count = [], [], 0
    for seg in segments:
        est = len(seg.source_text) // 3  # conservative for CJK
        if count + est > max_tokens and current:
            batches.append(current)
            current, count = [], 0
        current.append(seg)
        count += est
    if current:
        batches.append(current)
    return batches
```

### Pattern 4: Glossary Injection via Qwen-MT `terms`

**What:** Use the `terms` array in the `translation_options` parameter of each Qwen-MT call. Filter to only the terms whose source text appears in the current batch (avoids wasting token budget on irrelevant terms).

**Why not post-translation regex replacement:** Regex-replace after LLM output is fragile — the LLM may produce partial translations, inflected forms, or alternative capitalisations that the regex misses. The `terms` parameter instructs the model before generation.

**Why not constrained decoding:** Not available on DashScope.

```python
def build_terms_payload(glossary: list[dict], batch_text: str) -> list[dict]:
    lower = batch_text.lower()
    return [
        {"source": g["source"], "target": g["target"]}
        for g in glossary
        if g["source"].lower() in lower
    ]
```

### Pattern 5: One-Shot Reassembly on Export

**What:** The reassembler runs exactly once — when the user clicks "Export." Segment edits in the review UI are written to `segment.edited_text` in the DB. The reassembler reads `edited_text ?? translated_text` for each segment and writes it into the document.

**Why not incremental reassembly:** Partial document reassembly is harder than full reassembly and not needed for a PoC. Full reassembly on a 50-page DOCX takes < 2 seconds.

**Trade-offs:** The user cannot download a "live preview" during editing; they must trigger export. Acceptable for PoC.

---

## Data Flow

### DOCX Happy Path

```
1. User uploads file.docx + picks lang pair
   ↓
2. POST /jobs → saves file to disk, creates Job(status=PENDING) in DB
   ↓ enqueues job_id to ARQ
3. ARQ Worker picks up job_id
   ↓
4. Format Detector: reads magic bytes → "DOCX"
   ↓
5. DOCX Parser (python-docx):
   - Iterates document.paragraphs + tables
   - For each paragraph: captures (para_idx, style, runs)
   - For each run: captures (run_idx, text, bold, italic, font_size)
   - Emits Segment per PARAGRAPH (not per run — see Segment Boundaries)
   - Style context stores first run's formatting as reference
   ↓
6. Pre-processor:
   - Tags glossary terms with ⟦G:term_id⟧ markers (for verification only)
   - Replaces non-translatable tokens with ⟦T1⟧…⟦Tn⟧
   ↓
7. Batcher: groups segments into ≤7K-token batches
   ↓
8. Qwen-MT client (per batch):
   - POST to DashScope with model=qwen-mt-plus
   - translation_options.terms = [filtered glossary]
   - Retries on 429 with exponential back-off
   - Updates job.progress_pct in DB after each batch
   ↓
9. Post-processor (per segment):
   - Restores ⟦T1⟧…⟦Tn⟧ placeholders
   - Checks glossary term presence (warning only, not blocking)
   - Computes char-length ratio; sets segment.overflow_flag if ratio > 1.4
   - Writes translated_text to segment DB row
   ↓
10. Job.status → REVIEW_READY
    ↓
11. User opens side-by-side editor, edits segments → PATCH /jobs/{id}/segs/{seg_id}
    - Writes edited_text to DB
    ↓
12. User clicks Export → POST /jobs/{id}/export
    ↓
13. DOCX Reassembler (python-docx):
    - Opens original file as template
    - For each segment (by para_idx): clears all runs in the paragraph
    - Re-creates runs from translated/edited text, preserving style from style_context
    - Handles tables cell by cell (same pattern)
    - Saves to output path
    ↓
14. Response: 303 redirect to download URL
```

**Segment boundary for DOCX:** One segment = one paragraph. This is the natural OOXML translation unit — it preserves paragraph-level formatting (style, spacing, numbering) and gives the LLM a complete sentence or clause. Runs are recombined before sending and the first run's style is cloned to all output runs. Tables: one segment per cell (not per row) to avoid context bleed.

**Why not per-run segmentation:** Runs are typographic units, not semantic units. A single sentence can be split across 5 runs with different bold regions. Sending individual runs produces incoherent fragments.

---

### Scanned PDF Happy Path

```
1. User uploads scanned.pdf + picks lang pair
   ↓
2. POST /jobs → same as DOCX path
   ↓
3. ARQ Worker picks up job_id
   ↓
4. Format Detector: MIME = application/pdf
   ↓
5. Native-PDF probe (PyMuPDF):
   - Attempts text extraction from page 0
   - If text char count < 50 per page → classify as SCANNED
   ↓
6. OCR Subsystem (PaddleOCR PP-StructureV3):
   - Renders each page as 300 DPI image
   - Runs PP-StructureV3 → structured blocks with bounding boxes + confidence
   - Blocks with confidence < 0.6 → flagged with ocr_low_confidence=True
   - Output: ordered list of TextBlock(bbox, text, confidence, page_num)
   ↓
7. Segment extractor (pdf_scanned):
   - One segment per detected text block
   - Position stores {page_num, bbox} for overlay reconstruction
   ↓
8. Pre-processor → Qwen-MT client → Post-processor (same as DOCX)
   ↓
9. Scanned PDF Reassembler:
   PoC output choice: BILINGUAL PDF (page image + translated text column)
   - For each page:
     a. Embed original page image at left half
     b. Render translated text blocks at right half using reportlab/fpdf2
     c. Segments with ocr_low_confidence flagged with [?] prefix
   - No font/layout reconstruction (not feasible in PoC scope)
   ↓
10. Job.status → REVIEW_READY (review shows source OCR text + translation side-by-side)
    ↓
11. Export → download bilingual PDF
```

**PoC output choice — recommendation: bilingual PDF (original page image + translated text).**
This is the most honest output for a PoC:
- Option (a) "redraw layout": requires font matching, line-break reflow, bounding-box fitting — research-level effort, not a 2–3 week deliverable.
- Option (b) "bilingual PDF": shows the original page for reference while giving the translated content on the right. Reviewers trust it because the original is visible.
- Option (c) "plain text": loses page context entirely, not useful as a translation artifact.

Bilingual PDF is the correct PoC bar. It is also what the project brief explicitly names as acceptable.

---

### Native PDF Happy Path

```
1–4. Same as scanned PDF through format detection.
     ↓
5. Native-PDF probe: text char count ≥ 50/page → NATIVE PDF path
   ↓
6. PyMuPDF parser:
   - page.get_text("dict") → spans with bbox, font name, font size, text
   - Groups adjacent same-font spans into text blocks
   - Detects columns via x-coordinate clustering
   - One segment per block (contiguous text sharing same column position)
   ↓
7. Pre-processor → Qwen-MT client → Post-processor (same)
   ↓
8. Native PDF Reassembler (PyMuPDF):
   - Opens original PDF
   - For each segment: redacts original text region with page.add_redact_annot()
   - Calls page.apply_redactions()
   - Inserts translated text via page.insert_htmlbox(bbox, html_text, …)
     (insert_htmlbox handles font shaping, CJK, line wrapping automatically)
   - Sets overflow_flag if insert_htmlbox returns leftover text
   - Saves to output path
   ↓
9. Job.status → REVIEW_READY
```

**Native PDF caveat:** insert_htmlbox rewrites text inside the original bbox. Text that expands beyond the bbox is truncated and flagged. For PoC, flagging is the correct response — auto-shrinking font risks readability.

---

## Specific Architectural Questions — Answers

### Q1: Segment Boundaries Per Format

| Format | Unit | Rationale | Trade-off |
|--------|------|-----------|-----------|
| DOCX body | One paragraph | Natural OOXML semantic unit; run formatting preserved per first-run cloning | Long academic paragraphs can hit 600+ tokens; split at 500 tokens if needed |
| DOCX table | One cell | Prevents row context bleed; cells are independent semantic items | Very short cells (single word) may lose translation context — acceptable |
| PPTX | One text frame | A text box in a slide is already the minimum layout unit | A single slide can have 2–5 frames; send them as one batch with slide context |
| PPTX table | One cell | Same as DOCX tables | |
| Native PDF | One detected block | PyMuPDF's block = a set of spatially adjacent, same-column spans | Blocks can straddle paragraphs in multi-column layouts; heuristic may mis-split |
| Scanned PDF | One OCR text block | PP-StructureV3 block is the detection unit | OCR block boundaries may not align with sentence boundaries |

**Smaller units** (per-run, per-line) preserve style fidelity better but degrade translation quality because the LLM loses sentential context.
**Larger units** (per-page, whole-doc) improve translation quality but make reassembly and edit attribution impossible.
**Paragraph/block** is the correct PoC balance.

### Q2: Batching to Qwen-MT

Send **N segments per call** (adaptive batch), not one-per-call and not whole-doc.

- One-per-call: 500 API round-trips for a 50-page doc = unacceptably slow (even at 100ms/call = 50 seconds sequential).
- Whole-doc as one prompt: exceeds the 8,192 token limit for any non-trivial document.
- N segments per call: set N so total input tokens ≤ 7,000. Estimating ~3 chars/token for CJK-heavy text gives batches of ~20,000 chars. For typical DOCX paragraphs (~100 chars each), that is ~200 paragraphs per batch — comfortably one API call per chapter/section.

Format the batch as a numbered list prompt with each segment as `[1] <text>` and instruct Qwen-MT to return `[1] <translation>` etc. This lets the post-processor split on `[N]` markers reliably.

### Q3: Placeholder Protection

Use **Unicode private-use brackets** (`⟦T1⟧`) as placeholder tokens. Rationale:
- They are visually distinct from any natural-language character.
- They survive most tokenisers without being split.
- The post-processor can detect them with a simple regex.

Protect: URLs, `{{variable}}` template strings, numeric codes ≥ 5 digits, inline code spans (backtick-delimited), named HTML entities, email addresses.

Do NOT protect: numbers < 5 digits (translation should render them in target locale form), proper nouns already in the glossary (handled by the `terms` parameter).

Failure mode: model drops or reorders a marker. Post-processor detects missing/duplicate markers → marks segment with `placeholder_error=True` → reviewer sees warning in UI.

### Q4: Glossary Injection

**Primary approach: Qwen-MT `terms` parameter (prompt-level injection).**

Per API documentation (confirmed): `translation_options.terms` accepts an array of `{source, target}` pairs per request. The model uses this during generation — not regex-post-correction.

**Fallback: post-translation regex only** for critical brand names as a safety net (in case the model ignores a term). This is a simple `str.replace()` with case-insensitive matching, limited to proper nouns that are exact-match safe.

**Do not implement constrained decoding**: not available on DashScope.

**Filter terms per batch**: only inject terms whose source text appears in the batch. A 50-term glossary filtered to 3–5 relevant terms per batch consumes ~200 tokens — within budget.

### Q5: Text Expansion Handling

**For PPTX:** python-pptx supports `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` — set this on the text frame after translation. PowerPoint viewer will auto-shrink the font on open. For PoC, also set `overflow_flag=True` when char-length ratio > 1.3 so reviewers are alerted. Manual "re-prompt with length constraint" is not worth implementing for PoC.

**For native PDF:** PyMuPDF `insert_htmlbox()` returns leftover text when translation overflows the bbox. Detect this → set `overflow_flag=True` → in review UI, show the segment in orange.

**For DOCX:** Paragraphs reflow vertically — no overflow. Document length grows. No special handling needed.

**PoC response:** Flag first, fix manually second. Auto-font-shrink is safe for PPTX (it is the native PowerPoint behavior). Do not implement auto-shrink for PDF in the PoC.

### Q6: Job Progress

**Use polling (not WebSocket) for the PoC.**

The frontend polls `GET /jobs/{id}` every 2 seconds. The response includes `progress_pct` (0–100) and `status` (PENDING → PROCESSING → REVIEW_READY → EXPORTED). The worker increments `progress_pct` after each batch completes.

WebSocket/SSE adds meaningful complexity (connection lifecycle, reconnect logic, reverse proxy config) with little PoC benefit. A 50-page DOCX translates in 30–90 seconds; a 2-second poll interval gives 15–45 progress updates — sufficient for a progress bar.

Upgrade to SSE in v2 if users find polling sluggish.

### Q7: Review → Export

**Segments are persisted to DB on edit. Reassembly runs once on export.**

- `PATCH /jobs/{id}/segs/{seg_id}` with `{edited_text: "..."}` writes to `segment.edited_text`.
- On `POST /jobs/{id}/export`, the reassembler loads all segments for the job ordered by `segment.order`, uses `edited_text if edited_text else translated_text`, and produces the output file.
- Export is idempotent — can be called multiple times; overwrites the output file.
- The original source file is never mutated; it stays in storage as the template.

### Q8: Scanned PDF Output

**Recommendation: bilingual PDF (left = original page image, right = translated text).**

Rationale: honest, achievable in PoC scope, useful to reviewers. The reviewer sees the original scan for reference and the translated text for content. Low-confidence OCR segments are clearly flagged with `[?]` markers. Implementation uses `fpdf2` or `reportlab` to compose pages — no bounding-box layout reconstruction required.

---

## Anti-Patterns

### Anti-Pattern 1: In-Place Run Text Mutation in python-docx

**What people do:** `paragraph.text = translated` — this clears all run formatting.

**Why it's wrong:** Destroys bold, italic, font-size, hyperlink formatting from the original.

**Do this instead:** Clear runs, re-create them using the source segment's `style_context`. Clone the first run's font properties to all replacement runs. Accept that mid-sentence bold spans may not survive (PoC limitation, document in PITFALLS.md).

### Anti-Pattern 2: Sending Whole Documents to Qwen

**What people do:** Concatenate all paragraphs into one mega-prompt.

**Why it's wrong:** Hits the 8,192 token limit for any document over ~10 pages. Also makes per-segment result parsing unreliable.

**Do this instead:** Adaptive batching with numbered segment markers in the prompt. Parse output by `[N]` prefix.

### Anti-Pattern 3: Running OCR Synchronously in the API Request

**What people do:** Call PaddleOCR from the FastAPI route handler.

**Why it's wrong:** PaddleOCR PP-StructureV3 is CPU-heavy, takes 2–10 seconds per page. This blocks the event loop, times out Nginx, and crashes on large PDFs.

**Do this instead:** Enqueue everything to ARQ. The OCR step runs in the worker, which has no event-loop constraints.

### Anti-Pattern 4: Treating Segments as Immutable After Translation

**What people do:** Re-translate the entire document when a user edits one segment.

**Why it's wrong:** Wastes API calls; adds 30–90 second wait for each edit; costs money.

**Do this instead:** Store `edited_text` per segment in the DB. Reassembler always wins from `edited_text ?? translated_text`. Users can edit freely without re-triggering translation.

### Anti-Pattern 5: One API Call Per Segment

**What people do:** Loop over segments and `await translate(seg)` sequentially.

**Why it's wrong:** 500 sequential API calls at 150ms each = 75 seconds for a 50-page doc. 429 rate limits compound the problem.

**Do this instead:** Adaptive batching (Pattern 3). Optionally add `asyncio.gather()` for parallel batches if rate limits allow.

---

## Build Order (PoC Phases)

### Demo-blocking components (must have for AICore demo)

These unblock each other in dependency order:

```
Phase 1: Core Pipeline Skeleton
  ├── DB schema (Job, Segment, Glossary models)
  ├── Format detector
  ├── DOCX parser + segment extractor
  ├── Pre-processor (placeholder protection)
  ├── Qwen-MT client (batching + retry)
  ├── Post-processor (placeholder restore + overflow flag)
  ├── DOCX reassembler
  └── FastAPI: POST /jobs, GET /jobs/{id}, GET /jobs/{id}/segs
      ARQ worker wired end-to-end
  Deliverable: upload a DOCX, get a translated DOCX back

Phase 2: Review UX + Glossary
  ├── Frontend: upload form + job list + progress poll
  ├── Frontend: side-by-side segment review table (read-only first)
  ├── PATCH /jobs/{id}/segs/{seg_id} (edit persistence)
  ├── Frontend: inline edit in review table
  ├── Glossary CRUD (DB + API + simple frontend form)
  └── Export endpoint
  Deliverable: full DOCX workflow with review + glossary + download

Phase 3: PPTX + Native PDF
  ├── PPTX parser + reassembler (text-frame extraction, auto-fit)
  ├── Native PDF parser (PyMuPDF blocks) + reassembler (insert_htmlbox)
  └── Overflow flags surfaced in review UI
  Deliverable: all three hero formats working

Phase 4: Scanned PDF (OCR)
  ├── PaddleOCR PP-StructureV3 integration
  ├── Scanned PDF segment extractor
  ├── Bilingual PDF output (fpdf2)
  └── Low-confidence region flagging in review UI
  Deliverable: scanned PDF → bilingual output
```

### Nice-to-have (add if time remains)

- Progress percentage shown in frontend during translation (Phase 2 polling covers this, but a visual progress bar is polish)
- Font fallback handling for CJK glyphs in PDF reassembler
- Speaker notes translation in PPTX
- Re-translate single segment button in review UI
- DOCX footnote and endnote translation
- Docker-compose polish (health checks, volume mounts)

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Qwen-MT (DashScope) | `httpx.AsyncClient` with OpenAI-compatible endpoint or native DashScope SDK; `translation_options.terms` for glossary | 8,192 token/request limit; rate limits unstated — implement exponential back-off from day one |
| PaddleOCR PP-StructureV3 | In-process Python call (not an HTTP service) | GPU optional; CPU is slow but functional for PoC. Model download ~1 GB on first run — pin version |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| FastAPI ↔ ARQ Worker | Redis job queue (arq enqueue/dequeue) | Job ID is the shared key; worker writes progress_pct + status to DB |
| Worker ↔ Pipeline | Direct Python function calls (same process) | No inter-process messaging inside the worker |
| Pipeline ↔ Storage | File I/O (read source, write output) | Use configurable `STORAGE_ROOT` env var; swap to S3 with same interface post-PoC |
| Frontend ↔ API | HTTP REST (polling for status, PATCH for edits) | No WebSocket in PoC; upgrade to SSE in v2 |
| Reassembler ↔ Segments | DB query inside export endpoint (not in worker) | Export is triggered on-demand by the user, not automatically after translation |

---

## Scaling Considerations (informational — PoC is single-team internal)

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0–10 concurrent users (PoC) | Single FastAPI process, single ARQ worker, SQLite, local storage — adequate |
| 10–100 users | Postgres, multiple ARQ workers (one per CPU), S3 for storage, Redis Cluster |
| 100k+ requests | Horizontal worker scaling, job priority queues, translation cache (Redis), CDN for output files |

**First bottleneck for PoC:** The Qwen-MT API rate limit. Each batch call takes 0.5–2 seconds; a 50-page doc needs 5–20 batches = 2.5–40 seconds of API time. With one worker, second jobs queue behind first. For the demo, this is fine — single-user demo does not need parallel job execution.

---

## Sources

- Qwen-MT API documentation: https://www.alibabacloud.com/help/en/model-studio/machine-translation
  (Confirmed: `terms` parameter, 8,192 token limit, model variants: qwen-mt-plus, qwen-mt-flash, qwen-mt-lite)
- PyMuPDF large-PDF translation discussion: https://github.com/pymupdf/PyMuPDF/discussions/4395
  (Confirmed: `insert_htmlbox()` for reflow, page-range segmentation for performance)
- PaddleOCR PP-StructureV3: https://github.com/PaddlePaddle/PaddleOCR
  (PP-DocTranslation pipeline, layout detection, confidence scores, 109-language support)
- ARQ async job queue: https://github.com/python-arq/arq
  (Redis-backed, asyncio-native, natural FastAPI fit; maintenance-only mode noted)
- python-docx run-level text: https://python-docx.readthedocs.io/en/latest/user/text.html
  (Confirmed: must work at run level to preserve bold/italic; paragraph.text destroys formatting)
- python-pptx autofit: https://python-pptx.readthedocs.io/en/latest/dev/analysis/txt-autofit-text.html
  (MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE is the correct overflow response for PPTX)
- Document translation architecture reference: https://github.com/kukas/document-translation
  (Placeholder/markup extraction pattern, Okapi Framework precedent)

---
*Architecture research for: AI document translation PoC*
*Researched: 2026-04-17*
