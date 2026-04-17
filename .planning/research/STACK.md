# Stack Research

**Domain:** AI document translation web app (DOCX, PDF, PPTX) with LLM-based translation and format preservation
**Researched:** 2026-04-17
**Confidence:** HIGH (most items verified against official docs and live catalog)

---

## 1. Qwen Model Selection

### Verified DashScope Catalog (2026-04-17)

Source: https://www.alibabacloud.com/help/en/model-studio/models (live catalog)

| Model ID | Context Window | Input (Intl) | Output (Intl) | Recommended Use |
|----------|---------------|-------------|--------------|-----------------|
| `qwen-mt-turbo` | 1M tokens | $0.16/1M | $0.49/1M | PRIMARY — purpose-built for translation |
| `qwen-mt-plus` | 1M tokens | $2.46/1M | $7.37/1M | FALLBACK — highest quality for critical docs |
| `qwen3.5-plus` (alias: `qwen-plus-latest`) | 1M tokens | $0.40/1M | $2.40/1M | FALLBACK if MT models unavailable |
| `qwen3-max` | 262K tokens | $1.20/1M | $6.00/1M | Never use for bulk translation — cost prohibitive |

**The user wrote "qwen3.6-plus" — this model ID does NOT exist in the current catalog. The closest matches are `qwen3.5-plus` (released 2026-02-15) or the general-purpose `qwen-plus-latest` alias.**

### Recommendation

**Primary: `qwen-mt-turbo`** — Alibaba released a translation-specialized model (Qwen-MT) in 2025 built on Qwen3 with reinforcement learning on translation data. It supports 92 languages including Vietnamese, Japanese, Chinese (simplified/traditional), and English. It outperforms GPT-4.1-mini and Gemini-2.5-Flash on multilingual translation benchmarks at ~$0.49/M output tokens — dramatically cheaper than `qwen3-max`. It also supports a `terminology` parameter in the API for glossary injection natively.

**Fallback: `qwen-mt-plus`** — Same architecture, higher quality tier. Use for documents where quality is critical and cost is secondary (~15x the cost of turbo).

**Confidence: HIGH** — Verified against live DashScope billing page and Qwen official blog.

---

## 2. DashScope SDK vs OpenAI-Compatible Endpoint

### Recommendation: OpenAI-compatible endpoint + `openai` Python SDK

**Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` (Singapore region; appropriate for VNEXT)

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

response = client.chat.completions.create(
    model="qwen-mt-turbo",
    messages=[{"role": "user", "content": "..."}],
    extra_body={"terminology": {"source_lang": "en", "target_lang": "vi", "terms": [...]}}
)
```

**Why OpenAI SDK over `dashscope` SDK:**
- The `openai` SDK is already in Thu's stack (ICOM-P3 on Azure OpenAI). Zero new SDK to learn.
- The `dashscope` Python SDK has a separate async API surface that is less mature than `openai`'s native async support.
- The compatible endpoint supports `extra_body` for qwen-mt-turbo's `terminology` parameter, enabling native glossary injection.
- Easier to swap to Azure OpenAI or AWS Bedrock in a future PoC iteration.

**What NOT to use:** The `dashscope` SDK directly — it has a different method call pattern (`dashscope.Generation.call()`), does not benefit from the OpenAI ecosystem tooling (LangChain, LlamaIndex adapters), and adds a dependency with less community support.

**Confidence: HIGH** — Verified against official Alibaba Cloud compatibility docs.

---

## 3. OOXML Processing

### DOCX: python-docx 1.2.0

**Why:** Standard library for DOCX manipulation. Only library that directly reads/writes native Word XML without shelling out to LibreOffice.

**In-place text replacement pattern (correct approach):**

```python
from docx import Document

def translate_paragraph(para, translator_fn):
    # Collect full paragraph text across all runs
    full_text = "".join(run.text for run in para.runs)
    if not full_text.strip():
        return
    translated = translator_fn(full_text)
    # Write translated text into the FIRST run, clear the rest
    # This preserves paragraph-level style while avoiding run-split corruption
    if para.runs:
        para.runs[0].text = translated
        for run in para.runs[1:]:
            run.text = ""
```

**Critical gotchas:**

1. **Run splitting** (severity: HIGH) — Word auto-splits runs mid-word on formatting boundaries. A single word like "Hello" can span 3+ runs with identical formatting. Never translate `run.text` individually; always reconstruct the full paragraph text first and write back to `para.runs[0]`, blanking remaining runs. The `python-docx-replace` PyPI package handles this but is limited to find/replace; for translation, implement the pattern above.

2. **Tables** (severity: MEDIUM) — Table cells have their own paragraph objects. Must iterate `table.rows → row.cells → cell.paragraphs → paragraph.runs`.

3. **Tracked changes** (severity: LOW for PoC) — `<w:del>` and `<w:ins>` elements are not exposed by python-docx's API. They exist in the raw XML. For PoC, accept existing paragraphs (tracked changes do not survive translation anyway).

4. **Headers/footers** (severity: MEDIUM) — `doc.sections[i].header.paragraphs` and `.footer.paragraphs` — these are separate document parts, easy to miss.

5. **Text boxes / drawing anchors** (severity: MEDIUM) — Floating text boxes are not in `doc.paragraphs`; they are inside `<w:drawing>` elements in the body. Must traverse raw XML via `doc.element.body.iter()`.

6. **`p.text = value` is destructive** — Assigns all text to a single new run, nuking ALL run-level formatting (bold, italic, font, color). Never use `paragraph.text` setter.

**What NOT to use:** `docx2txt` — text-only extraction, destroys all formatting.

### PPTX: python-pptx 1.0.2

**Critical gotchas:**

1. **SmartArt** (severity: HIGH) — SmartArt nodes are stored as `<p:sp>` shapes with `<p14:creationId>` markers. `python-pptx` exposes the `text_frame` property on SmartArt shapes, but modifying it can corrupt the graphic structure. For PoC: extract text from SmartArt, translate, write back via `text_frame.paragraphs[i].runs[j].text` — same run-splitting issue as DOCX applies.

2. **Speaker notes** (severity: LOW) — `slide.notes_slide.notes_text_frame` — accessible but separate object.

3. **Tables** (severity: MEDIUM) — `shape.table.cell(row, col).text_frame` — same run pattern.

4. **Text overflow** (severity: HIGH for PPTX) — Unlike DOCX where text wraps freely, PPTX text boxes have fixed dimensions. Translated text 20-40% longer will overflow. Detect with `text_frame.auto_size`; set `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` to auto-shrink, or flag overflow for human review.

5. **Charts** — Chart data labels are stored in embedded XLSX (`pptx/charts/data1.xlsx`). python-pptx does not expose these via its API. For PoC, skip chart text translation (not worth the complexity).

6. **Grouped shapes** — Must recurse into `shape.shapes` when `shape.shape_type == MSO_SHAPE_TYPE.GROUP`.

**What NOT to use:** `python-pptx-text-replacer` PyPI package — useful for find/replace but not designed for full translation workflows; use raw python-pptx and implement paragraph-level loops.

**Confidence: HIGH** — Verified with Context7 (python-pptx official docs), supplemented by WebSearch.

---

## 4. Native PDF Translation

### Recommendation: PyMuPDF 1.26.x (primary) + pdf2docx 0.5.x (round-trip alternative)

**Path A — PyMuPDF in-place redact + reinsert (recommended for PoC)**

PyMuPDF is the fastest and most capable Python PDF library. Its redaction API is the standard approach for text replacement:

```python
import pymupdf

doc = pymupdf.open("input.pdf")
for page in doc:
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        for line in block.get("lines", []):
            for span in line["spans"]:
                original_text = span["text"]
                rect = pymupdf.Rect(span["bbox"])
                translated = translate(original_text)
                page.add_redact_annot(rect, fill=(1, 1, 1))  # white out
    page.apply_redactions()
    # Re-insert translated text at span positions
    # WARNING: font from original span is not re-usable
    page.insert_textbox(rect, translated, fontname="helv", fontsize=span["size"])
doc.save("output.pdf")
```

**Key caveats:**
- **Font mismatch** — Original embedded fonts are not re-usable. Must bundle substitute fonts (see Section 10). For CJK/VN, embed Noto Sans CJK or similar.
- **Text expansion overflow** — `page.insert_textbox()` returns negative if text overflows the rect. Must detect and either shrink font or flag for review.
- **Complex scripts** — For right-to-left languages (Arabic, Hebrew), use `page.insert_htmlbox()` instead of `page.insert_textbox()` to preserve shaping. Vietnamese is LTR so `insert_textbox` works.
- **Multi-column layouts** — Block extraction order may not match reading order. Use `sort=True` in `get_text()` for reading-order sorting.

**Path B — pdf2docx round-trip (simpler but lower fidelity)**

```
scanned or complex PDF → pdf2docx → DOCX → translate with python-docx → export to PDF via LibreOffice headless
```

pdf2docx 0.5.8 (MIT, maintained by community after Artifex handed off) converts PDF to DOCX preserving structure. Then translate DOCX (Path A of DOCX pipeline), then convert back to PDF with LibreOffice headless (`libreoffice --headless --convert-to pdf output.docx`).

**When to use round-trip:** Multi-column academic papers, docs with complex inline figures. The round-trip adds 2 conversion steps = 2x opportunities for fidelity loss, so use only when direct PyMuPDF insertion fails acceptably.

**Comparison:**

| Tool | Layout fidelity | Speed | CJK/VN font | Round-trip |
|------|---------------|-------|-------------|-----------|
| PyMuPDF | HIGH (direct) | Very fast | Requires bundled fonts | No |
| pdfplumber | MEDIUM (extraction only, no write) | Medium | N/A | N/A |
| pdf2docx | MEDIUM | Slow | Inherited from LibreOffice | Yes |
| pypdfium2 | HIGH (extraction) | Very fast | No write API | No |

**What NOT to use:** `pdfplumber` for translation — it has no write/reinsertion API. Use it only for table extraction. `pypdfium2` similarly has no text reinsertion. `camelot` — tables only.

**Confidence: HIGH** — Verified via PyMuPDF official docs (Context7) and GitHub discussion threads from 2025.

---

## 5. OCR for Scanned PDFs

### Recommendation: PaddleOCR 3.x (PP-OCRv5) as default; Azure Document Intelligence as cloud alternative

**PaddleOCR PP-OCRv5 (recommended for PoC)**

- Supports 106 languages including Vietnamese, Japanese, Chinese (Simplified + Traditional), English in a single model.
- PP-OCRv5 (PaddleOCR 3.0, released 2025) achieves +13 percentage points over PP-OCRv4 on complex doc benchmarks; +30% improvement for multilingual text recognition vs PP-OCRv3.
- Self-hostable, zero per-page cost, GPU-accelerated inference available.
- The PP-StructureV3 pipeline handles layout analysis (reading order, tables, figures) — critical for producing usable OCR output.

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_doc_orientation_cls=True, lang="ch")  # ch model covers CJK+Latin
result = ocr.ocr("scanned_page.png", cls=True)
```

**Language-specific notes:**
- Vietnamese: Covered by the `latin` or `ch` model (PaddleOCR treats VN as Latin-script). PP-OCRv5 includes VN in its multilingual pack.
- Japanese/Chinese: Native support in `ch` model (covers CJK). PP-OCRv5 shows 13+ point improvement for Japanese detection vs v4.
- Mixed-language docs: Use `ch` model which handles CJK + Latin mixed content.

**Azure Document Intelligence (cloud fallback)**

Use when: self-hosting GPU is not available, or when the doc contains complex tables/forms that need structured extraction beyond basic OCR.
- Read model supports VN, JA, ZH, EN with high accuracy on real-world scanned docs.
- $1.50/1000 pages for standard Read (free tier: 500 pages/month).
- Returns JSON with bounding boxes, reading order, table structure — easier to post-process.
- Data routed through Azure: acceptable for internal VNEXT PoC; flag if AICore has data residency concerns.

**Ranking for this PoC (VN + JA + ZH + EN):**

| OCR Engine | VN quality | JA/ZH quality | Self-host | Cost | Ease | Verdict |
|-----------|-----------|--------------|---------|------|------|---------|
| PaddleOCR PP-OCRv5 | HIGH | HIGH | Yes | Free | Medium | **Recommended default** |
| Azure Document Intelligence | HIGH | HIGH | No | $1.50/1K pp | Easy | Cloud fallback |
| Tesseract 5 + pytesseract | MEDIUM | MEDIUM (JA poor) | Yes | Free | Easy | Not recommended for JA |
| Google Document AI | HIGH | HIGH | No | $1.50/1K pp | Easy | Alternative to Azure |
| Alibaba OCR (DashScope) | HIGH (CN-biased) | HIGH | No | Varies | Medium | DashScope ecosystem bonus |

**What NOT to use:** `pytesseract` alone — Tesseract's Japanese model is significantly weaker than PaddleOCR for scanned docs with mixed scripts. It also requires per-language model files manually installed.

**Confidence: HIGH (PaddleOCR)** — Verified via PP-OCRv5 technical report (arXiv 2507.05595) and official PaddleOCR docs. **MEDIUM (Azure DI)** — Based on Microsoft official docs + known production use.

---

## 6. Glossary / Terminology Injection

### Recommendation: Native qwen-mt-turbo `terminology` parameter + prompt-level fallback

**Layer 1 — Native API terminology (use this first)**

`qwen-mt-turbo` exposes a `terminology` field in `extra_body` that accepts source→target term pairs and enforces their use in translation output without consuming prompt tokens:

```python
response = client.chat.completions.create(
    model="qwen-mt-turbo",
    messages=[...],
    extra_body={
        "terminology": {
            "source_lang": "en",
            "target_lang": "vi",
            "terms": [
                {"source": "RAG", "target": "RAG"},
                {"source": "retrieval-augmented generation", "target": "sinh tăng cường truy xuất"},
            ]
        },
        "domains": "technology"
    }
)
```

This is the cleanest path: no prompt bloat, no post-processing, native enforcement.

**Layer 2 — Prompt-level term dictionary (fallback for non-MT models)**

If using `qwen3.5-plus` or similar general-purpose model, inject the glossary in the system prompt:

```
System: You are a professional translator. Translate the following text from {source_lang} to {target_lang}.
Preserve all formatting markers exactly.
Required terminology (always use these exact translations):
{term_pairs_formatted}
```

Include only terms relevant to the current document chunk (filter by keyword match) to keep prompt size bounded. A chunk of 20-50 relevant term pairs is practical.

**Layer 3 — Post-processing find/replace (safety net)**

After LLM output, do a deterministic find/replace pass for critical terms. Use `re.sub()` with word-boundary anchors for accuracy. This catches cases where the LLM paraphrases rather than term-matches.

**Storage:** Store glossaries as simple key-value JSON in the DB (per-job or user-uploaded CSV). No RAG needed for PoC — the glossary per document is small enough to fit in the prompt directly.

**What NOT to use:** Constrained decoding / grammar-based forcing — too complex for a 2-3 week PoC, and qwen-mt's native terminology support makes it unnecessary. Translation memory / fuzzy-match reuse — explicitly deferred in PROJECT.md.

**Confidence: MEDIUM** — qwen-mt-turbo terminology API confirmed via official Qwen-MT blog post. Prompt injection pattern is well-established in literature (WMT24 papers).

---

## 7. FastAPI + Next.js for Long-Running Jobs

### File Upload Handling

Use FastAPI's `UploadFile` with chunked streaming for large documents. Hard cap at 50MB for PoC (PPTX/PDF rarely exceed this). No virus scan for internal PoC — document it as a known gap.

```python
@router.post("/jobs/", status_code=201)
async def create_translation_job(
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
):
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 50MB limit")
    contents = await file.read()
    # Store to MinIO / local, enqueue job
```

### Background Job Queue: arq 0.26.x + Redis

**Recommendation: arq over Celery for this project.**

Rationale:
- Thu's stack is already async-first (FastAPI, asyncio, async SQLAlchemy). arq workers run in the same asyncio event loop — no sync/async bridge needed.
- arq is significantly lighter than Celery: no separate Beat process, no broker config complexity, single Redis dependency already in Thu's existing stack.
- arq v0.27 supports job result retrieval and status polling natively via `job.result()` and `job.status()`.
- Celery's async support (via `celery[async]`) is bolted on and less clean.

**Important caveat:** arq is in "maintenance only" mode as of 2026. It is stable and maintained for bug fixes but not gaining new features. For a 2-3 week PoC this is acceptable — it will not break. If the project evolves to production, evaluate migration to Celery or a managed queue.

```python
# worker.py
async def translate_document(ctx, job_id: str, file_path: str, ...):
    await update_job_status(job_id, "processing")
    result = await run_translation_pipeline(file_path, ...)
    await update_job_status(job_id, "done", result_path=result)

class WorkerSettings:
    functions = [translate_document]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 4  # limit concurrency for memory-hungry PDF processing
```

**What NOT to use:** FastAPI `BackgroundTasks` — no job status, no retry, no persistence across restarts. Not viable for 30-second+ translation jobs. RabbitMQ — overkill for PoC and adds operational overhead beyond what arq+Redis costs.

### Job Status: SSE (Server-Sent Events)

**Recommendation: SSE over polling, over WebSockets.**

- SSE is simpler than WebSockets (one-directional push, no upgrade dance).
- FastAPI 0.135+ has native SSE support via `EventSourceResponse` (no external lib needed).
- The client uses `@microsoft/fetch-event-source` (npm) since native `EventSource` does not support custom headers.
- Pattern: client connects to `/jobs/{job_id}/stream` on upload, SSE endpoint polls Redis/DB every 1s and pushes `{status, progress_pct, message}` events until terminal state.

```python
from fastapi import Request
from fastapi.responses import EventSourceResponse

@router.get("/jobs/{job_id}/stream")
async def stream_job_status(job_id: str, request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            job = await get_job(job_id)
            yield {"data": job.model_dump_json()}
            if job.status in ("done", "failed"):
                break
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator())
```

### Side-by-Side Review UI

**Recommendation: `@monaco-editor/react` 4.x with the built-in `DiffEditor` component.**

Monaco is VS Code's editor engine — it handles all text content including CJK and Vietnamese without additional configuration. The `DiffEditor` component renders source (left) and translation (right) with inline highlights.

- For the PoC, render translated text as plain text in the diff panel (not the formatted document). Full WYSIWYG document diff is out of PoC scope.
- Allow inline edits in the right pane before export.
- `@monaco-editor/react` works with Next.js without any webpack config — load with `dynamic(() => import(...), { ssr: false })` since Monaco requires browser APIs.

**Alternatives considered:**
- `react-diff-viewer` — simpler but text-only, no editing capability.
- iframe-based document preview — requires WASM PDF renderer (complex for PoC).

**What NOT to use:** `react-diff-viewer-continued` — simpler and read-only, no inline editing.

**Confidence: HIGH (arq, SSE, Monaco)** — All three verified against official docs and current usage patterns.

---

## 8. File Storage

### Recommendation: Local filesystem for Phase 1; MinIO (Docker) for Phase 2+

**Phase 1 (first 1-2 weeks):** Local filesystem (`/app/storage/{job_id}/`) mounted as a Docker volume. Zero setup, zero latency. Sufficient for a single-machine PoC demo.

```python
STORAGE_ROOT = Path("/app/storage")

async def save_upload(job_id: str, filename: str, content: bytes) -> Path:
    path = STORAGE_ROOT / job_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
```

**Phase 2 (if demo moves to multi-machine or needs persistence guarantees):** MinIO in Docker Compose with the `boto3`/`aioboto3` client (S3-compatible). The code change from local→MinIO is minimal if you abstract storage behind a `StorageService` protocol from day one.

**What NOT to use:** AWS S3 or Azure Blob for the PoC — adds cloud billing overhead, IAM config complexity, and data egress concerns. MinIO is 100% S3-compatible locally.

**Confidence: HIGH**

---

## 9. Database

### Recommendation: PostgreSQL 16 + SQLAlchemy 2.0 async + asyncpg + Alembic

**Why PostgreSQL over SQLite:**
- arq uses Redis for job queue, but job metadata (status, file paths, glossaries, language pairs, timestamps, output paths) needs a relational DB.
- SQLite has write serialization — only one writer at a time. With concurrent translation jobs each updating status, this becomes a bottleneck.
- Thu already runs PostgreSQL in both production projects (scala-i-ask, ICOM-P3) — no new operational knowledge needed.
- Docker Compose makes local PostgreSQL trivial to run.
- asyncpg is the fastest async PostgreSQL driver in Python (binary protocol).

**Stack:**
- `SQLAlchemy 2.0` + `asyncpg` driver (`postgresql+asyncpg://`)
- `SQLModel` 0.0.21+ (SQLAlchemy 2.0 + Pydantic v2 integration) — appropriate if Thu wants Pydantic models to double as ORM models
- Alternatively, raw SQLAlchemy 2.0 async with separate Pydantic schemas (clearer separation)
- `Alembic` for migrations

**Schema hint:**
- `jobs` table: id, status, source_lang, target_lang, input_path, output_path, created_at, updated_at, error_msg
- `glossaries` table: id, name, terms (JSONB), created_at
- `job_glossaries` join table

**What NOT to use:** SQLite for the arq job metadata store — arq already needs Redis; adding SQLite creates a second storage system with write contention. MongoDB — no benefit over PostgreSQL JSONB for this schema.

**Confidence: HIGH**

---

## 10. Font Handling for CJK + Vietnamese PDFs

### Recommendation: Bundle Noto fonts; use PyMuPDF font embedding

**The problem:** When PyMuPDF reinserts text after redaction, the original embedded fonts are inaccessible for new text insertion. For Vietnamese (Latin-script with diacritics), Japanese (kanji, hiragana, katakana), and Chinese (CJK), missing fonts produce boxes or garbled output.

**Solution: Bundle these fonts in the Docker image:**

| Font | Coverage | Size | Source |
|------|---------|------|--------|
| `NotoSansCJK-Regular.ttc` | Japanese, Chinese (SC/TC), Korean | ~48MB | noto-cjk GitHub |
| `NotoSans-Regular.ttf` | Vietnamese + Latin | ~500KB | Google Fonts / noto-fonts |
| `NotoSerif-Regular.ttf` | Serif variant for body text | ~500KB | Google Fonts |

**PyMuPDF font registration:**
```python
# Register bundled font for text insertion
fontfile = "/app/fonts/NotoSansCJK-Regular.ttc"
page.insert_text(
    point,
    translated_text,
    fontfile=fontfile,
    fontname="noto-cjk",
    fontsize=span["size"],
)
```

**For DOCX/PPTX output:** python-docx and python-pptx embed font references by name. If the reviewer's machine does not have the referenced font installed, Word will substitute. For demo purposes this is acceptable. For the translated PDF download via LibreOffice headless, install the Noto fonts in the Docker image.

**LibreOffice headless font install (Dockerfile):**
```dockerfile
RUN apt-get install -y fonts-noto-cjk fonts-noto && fc-cache -f
```

**Risks:**
- `NotoSansCJK-Regular.ttc` is ~48MB — increases Docker image size. Accept this for correctness.
- Font metrics differ from original PDF fonts — line heights and character widths will not match exactly. This is unavoidable without the original font license.
- For scanned PDFs (OCR output), use a clean Noto Sans layout — the original font is unknowable anyway.

**What NOT to use:** ReportLab for CJK output — CJK support is poor and requires manual glyph registration. fpdf2 is better (Unicode subsetting via harfbuzz) but the round-trip through PyMuPDF is more straightforward for this use case.

**Confidence: MEDIUM** — Font handling approach verified via PyMuPDF docs and fpdf2 docs. Specific Noto font file sizes are from noto-cjk GitHub.

---

## Recommended Stack Summary

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | Latest stable; asyncio improvements |
| FastAPI | 0.115+ | API framework | Already in Thu's stack; native async |
| Next.js | 15 (App Router) | Frontend | Already in Thu's stack (ICOM-P3) |
| PostgreSQL | 16 | Job + glossary DB | Already in Thu's stack; JSONB for terms |
| Redis | 7 | arq queue broker | Already in Thu's stack |
| Docker Compose | 2.x | Local orchestration | Single-machine PoC deployment |

### AI / Translation

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `qwen-mt-turbo` (DashScope) | — | Primary translation engine | Translation-specialized, 92 languages, cheapest Qwen tier |
| `qwen-mt-plus` (DashScope) | — | High-quality fallback | Same as turbo but higher quality tier |
| openai SDK | 1.x | DashScope client | OpenAI-compatible endpoint; Thu already uses it |

### Document Processing

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| python-docx | 1.2.0 | DOCX read/write | Run-level text replacement |
| python-pptx | 1.0.2 | PPTX read/write | Shape/table/notes traversal |
| PyMuPDF (pymupdf) | 1.26.x | PDF extraction + reinsertion | Redact-and-reinsert pattern |
| pdf2docx | 0.5.8 | Complex PDF → DOCX round-trip | Fallback for column-heavy layouts |
| PaddleOCR | 3.x (PP-OCRv5) | Scanned PDF OCR | Best OSS multilingual quality |

### Backend Infrastructure

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| arq | 0.27.0 | Async job queue | Maintenance mode but stable; asyncio-native |
| SQLAlchemy | 2.0.x | Async ORM | With asyncpg driver |
| asyncpg | 0.30.x | PostgreSQL async driver | Fastest binary-protocol driver |
| Alembic | 1.x | DB migrations | Standard with SQLAlchemy |
| sse-starlette | 3.3.4 | SSE job status streaming | Or FastAPI 0.135+ built-in |
| pydantic-settings | 2.x | Config from env | SecretStr for API keys |
| uv | — | Package management | Per Thu's global preference |

### Frontend

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| @monaco-editor/react | 4.x | Side-by-side diff + edit UI | DiffEditor component; CJK-safe |
| @microsoft/fetch-event-source | 2.x | SSE client with auth headers | EventSource substitute |
| TanStack Query | 5.x | Server state management | Job status polling + SSE |

### Fonts (Docker image)

| Asset | Purpose | Install |
|-------|---------|---------|
| fonts-noto-cjk | JA/ZH PDF text insertion | `apt-get install fonts-noto-cjk` |
| fonts-noto | VN/Latin PDF text insertion | `apt-get install fonts-noto` |

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `qwen-mt-turbo` | `qwen3.5-plus` | qwen-mt-turbo is specialized for translation; cheaper; native terminology API |
| openai SDK + compatible endpoint | `dashscope` SDK | openai SDK already in Thu's stack; richer ecosystem |
| PaddleOCR PP-OCRv5 | Tesseract 5 | Tesseract's Japanese model is materially weaker; no native layout analysis |
| arq + Redis | Celery + Redis | Celery's async support is a bolt-on; arq is asyncio-native |
| arq + Redis | FastAPI BackgroundTasks | BackgroundTasks has no persistence, no status polling, no retry |
| PostgreSQL | SQLite | SQLite write serialization bottlenecks concurrent job updates |
| PyMuPDF (direct reinsertion) | pdfplumber | pdfplumber has no text write API; extraction only |
| Local FS → MinIO | AWS S3 | Adds cloud cost + IAM config for an internal PoC |
| Monaco DiffEditor | react-diff-viewer | react-diff-viewer is read-only; Monaco enables inline editing before export |
| LibreOffice headless | docx2pdf (Windows COM) | COM automation requires Windows; LibreOffice works on Linux Docker |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `qwen3-max` for bulk translation | $6/1M output tokens — 10x the cost of qwen-mt-turbo for inferior translation quality | `qwen-mt-turbo` |
| `qwen-turbo` (old) | Explicitly deprecated by Alibaba; migrate to `qwen-flash` per docs | `qwen-mt-turbo` or `qwen3.5-flash` |
| `paragraph.text = value` in python-docx | Destroys all run-level formatting (bold, italic, font, color) | Overwrite `run.text` with translated value in first run, blank remaining runs |
| Tesseract for Japanese | Weak JA model; no layout analysis | PaddleOCR PP-OCRv5 |
| FastAPI `BackgroundTasks` for translation jobs | No persistence, no status API, dies on restart | arq + Redis |
| `dashscope` SDK | Less mature async, breaks OpenAI ecosystem tooling | openai SDK with compatible base_url |
| `pdf2docx` as primary path | Abandoned by Artifex; community-maintained; 2-step fidelity loss | PyMuPDF direct reinsertion |
| ReportLab for CJK PDF generation | Poor CJK support; requires manual glyph registration | PyMuPDF with bundled Noto fonts |
| Embedding fonts from original PDF | Legally and technically not allowed; fonts are DRM-protected | Bundle Noto Sans CJK as substitute |

---

## Installation (uv)

```bash
# Backend core
uv add fastapi uvicorn[standard] pydantic-settings

# Translation + LLM
uv add openai

# Document processing
uv add python-docx python-pptx pymupdf pdf2docx paddlepaddle paddleocr

# Async infrastructure
uv add arq redis sqlalchemy asyncpg alembic sqlmodel

# Job status streaming
uv add sse-starlette

# Frontend (in /frontend)
npm install @monaco-editor/react @microsoft/fetch-event-source @tanstack/react-query

# Fonts (Dockerfile)
# RUN apt-get install -y fonts-noto-cjk fonts-noto && fc-cache -f
```

---

## Version Compatibility Notes

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| python-docx 1.2.0 | python 3.8–3.13 | No breaking change from 1.1.x |
| python-pptx 1.0.2 | python 3.8–3.13 | 1.0.x has breaking changes from 0.6.x — don't downgrade |
| PyMuPDF 1.26.x | python 3.10–3.14 | Requires `PyMuPDFb` wheel (auto-installed by pip) |
| arq 0.27.0 | python 3.9–3.11 officially | 3.12 works in practice; verify before pinning |
| SQLAlchemy 2.0 | asyncpg 0.29+ | Use `postgresql+asyncpg://` DSN |
| PaddleOCR 3.x | paddlepaddle 3.0+ | Must match paddle version exactly |
| openai 1.x | python 3.8+ | DashScope compatible mode confirmed |

---

## Sources

- Alibaba Cloud Model Studio — Live model catalog: https://www.alibabacloud.com/help/en/model-studio/models
- Alibaba Cloud DashScope billing: https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio
- Alibaba Cloud OpenAI compatibility docs: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- Qwen-MT official blog: https://qwenlm.github.io/blog/qwen-mt/
- PyMuPDF official docs (Context7 verified): https://pymupdf.readthedocs.io/en/latest/
- python-docx 1.2.0 docs (Context7 verified): https://python-docx.readthedocs.io/
- python-pptx 1.0.2 docs (Context7 verified): https://python-pptx.readthedocs.io/
- PaddleOCR PP-OCRv5 technical report: https://arxiv.org/abs/2507.05595
- arq PyPI: https://pypi.org/project/arq/
- sse-starlette PyPI: https://pypi.org/project/sse-starlette/
- FastAPI SSE docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/

---
*Stack research for: AI document translation web app*
*Researched: 2026-04-17*
