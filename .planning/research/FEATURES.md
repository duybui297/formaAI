# Feature Research

**Domain:** AI document translation (web app, PoC stage)
**Researched:** 2026-04-17
**Confidence:** HIGH (competitive scan verified across 8+ products; architecture claims cross-checked)

---

## Competitive Scan

The following products were surveyed to establish what features are commodity versus genuinely differentiating.

| Product | Category | Formats | Glossary | Review UX | Standout |
|---------|----------|---------|----------|-----------|----------|
| **Azure AI Translator — Document Translation API** | Commodity ML API | DOCX, PPTX, XLSX, PDF, HTML, TXT, images (2026 batch) | Yes — TSV/TMX file upload per job | None — API only, no UI | Batch async, Azure Blob storage integration, blazing fast, 90+ languages |
| **DeepL Document Translation** | Consumer/Pro SaaS | DOCX, PPTX, XLSX, PDF, TXT, XLIFF, SRT, HTML | Yes — glossary_id per request; TSV/TMX upload | None in free; Pro has basic editable output | High perceived quality; output_format param lets PDF→DOCX conversion |
| **Google Translate (web)** | Consumer web | DOCX, PDF, PPTX, XLSX, TXT (10 MB limit) | None | None — download only | Largest language coverage; worst format preservation on complex PDFs (flattens to text blocks) |
| **DocTranslator.com** | Consumer web | DOCX, PPTX, XLSX, PDF (20 MB free) | Yes — per-project glossary + translation memory | None — download only | Claims "Excellent" layout rating; actually Google Translate under the hood |
| **Lilt** | Enterprise TMS | Broad (via connectors) | Yes — domain-specific TMs + adaptive MT | Full CAT tool with segment-level review, live-learning from edits | Adaptive AI that learns from human edits in real-time |
| **Smartling** | Enterprise TMS | Broad (50+ formats) | Yes — hard rules + AI-enhanced inflection-aware insertion | Review Mode (proofread) + CAT Tool (edit + glossary); approve/reject workflow | RAG-enhanced prompts inject TM + glossary into LLM; AI-Enhanced Glossary Term Insertion |
| **Phrase (Memsource)** | Enterprise TMS/CAT | 50+ formats | Yes — centralized terminology management, auto checks | Full CAT tool; real-time multi-user collaboration | 500+ languages; integrates 30+ MT engines; GPT for post-editing |
| **Intento** | Enterprise ML router | Varies (via provider) | Yes — provider-agnostic glossary layer; enforces even when provider lacks native support | LQA feedback (automated quality assessment) | MT router + generative AI; multi-agent QA pipeline |
| **PDFMathTranslate / BabelDOC** | Open-source CLI/GUI | PDF (scientific papers) | No | No — CLI/GUI only | Bilingual side-by-side PDF output; layout coordinates preserved; 25k GitHub stars |
| **LibreTranslate / Argos Translate** | Open-source API | Text + basic file via argos-translate-files | No | No | Self-hosted, offline capable; quality well below commercial |
| **immersive-translate** | Browser extension | Web pages + EPUB + PDF (browser) | Per-domain rules | None | Bilingual inline overlay; very popular for reading, not authoring |

**Key insight:** Every commodity tool (Azure, DeepL, Google) handles DOCX reasonably well but breaks on complex PDF layouts. None offer a review UI. Glossary is an API-only option in commodities — no enforcement intelligence. The enterprise TMS tools (Lilt, Smartling, Phrase) have polished review UX but are months of setup, not PoC speed.

---

## Feature Landscape

### Table Stakes (Audience Expects These — Demo Falls Flat Without Them)

These are the things AICore reviewers will check in the first 5 minutes. Absence signals an incomplete PoC, not a design choice.

| Feature | Why Expected | Complexity | PoC Approach |
|---------|--------------|------------|--------------|
| **File upload (drag-drop)** | Every competitor has it; it is the entry point of the demo | LOW | Single-file drag-drop; no batch needed for PoC |
| **Source language auto-detect** | Reviewers will not want to select source language for obvious documents | LOW | Pass `detect_language` flag to Qwen or use a lightweight langdetect library as pre-check |
| **Target language picker** | Core selection step; must be present | LOW | Dropdown with common pairs first (EN, VI, JA, ZH, KO); fallback to full list |
| **Translation progress indicator** | Large files take 30–120 s; blank screen = broken in reviewers' minds | LOW | Polling or SSE progress bar with stage labels (parsing / translating / rebuilding) |
| **Download translated file in original format** | Reviewers need the output file — this is the whole point | LOW-MEDIUM | Return DOCX/PDF/PPTX in original format; trigger browser download |
| **DOCX translation with format preservation** | This is the declared hero format; any miss here kills the demo | HIGH | python-docx text-run replacement; preserve runs, styles, tables, headers/footers |
| **Native PDF translation with layout fidelity** | Second hero format; reviewers will upload PDFs | HIGH | PyMuPDF extraction → Qwen translation → PDF reconstruction (reportlab or fpdf2); flag complex pages |
| **Error state: unsupported format / too large** | Upload an unsupported file → silent failure = bad UX | LOW | Clear error toast with format list |
| **Basic job status (pending / translating / done / failed)** | Long async job needs state communication | LOW | Simple status polling endpoint; store job state in-process or Redis |

### Differentiators (The Four Capabilities That Win the Demo)

These are explicitly called out by the user as the angles that beat commodity MT. They are the reasons to build this instead of "wrapping Azure."

#### D1: LLM Translation Quality

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Qwen LLM as translation engine** | Measurably better than commodity NMT on natural phrasing, domain awareness, multi-lingual nuance (especially CJK + SEA) | MEDIUM | Use `qwen-plus` or `qwen-max` via DashScope OpenAI-compatible API; segment batching critical for throughput |
| **Segment-batching with document context** | Individual segment calls lose cross-reference context; batching by paragraph/section keeps coherence | MEDIUM | Batch ~10–20 segments per call with a sliding context window; include document title + surrounding paragraphs in system prompt |
| **System prompt with domain + style instructions** | "Translate formally for business documents" outperforms bare translation by 15–30% in perceived quality | LOW | Per-job system prompt injection; show the prompt in the review UI to signal transparency |
| **Language pair quality transparency** | Surface "this pair is well-supported by the model" vs "experimental" | LOW | Hard-code a known-good pairs list (EN↔VI, EN↔ZH, EN↔JA, EN↔KO) as "recommended"; others get "may need review" badge |

#### D2: Glossary / Terminology Control

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Glossary upload (CSV/TSV: source term → target term)** | Enterprise docs have company names, product names, acronyms that must not be free-translated | MEDIUM | Parse CSV; store per-job glossary dict; inject into every segment prompt |
| **Prompt-injection enforcement** | "The following terms MUST be translated exactly as shown: [term list]" appended to system prompt | LOW | Simple string construction; works well with instruction-following models like Qwen |
| **Glossary hit highlighting in review UI** | Show reviewer which segments used glossary terms; build trust in enforcement | MEDIUM | Tag segments where glossary substitution occurred; highlight in review pane |
| **Conflict flagging** | If LLM ignores a glossary term (detectable by string comparison post-translation), flag that segment | MEDIUM | Post-process: regex check each translated segment against expected glossary targets; mark segments with mismatches |

#### D3: Smart Layout Handling

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Text-expansion detection for PPTX text boxes** | Translations are 20–40% longer; text that overflows a text box silently ruins slide decks | MEDIUM | python-pptx: after inserting translated text, compare rendered text height vs box height; flag overflow |
| **Auto-scale font size on overflow (safe range)** | Font 12 → 10 is acceptable; font 12 → 6 is not — auto-scale within a threshold | MEDIUM | Apply `shrink_text_on_overflow` or recalculate `font.size` iteratively; cap shrink at 80% of original |
| **Overflow warning in review UI** | If auto-scale isn't enough, reviewer needs to know which slides need manual attention | LOW | Attach `overflow: true, shrink_applied: float` metadata per text box; show warning icons in review UI |
| **DOCX table cell overflow flag** | Tables with narrow columns can overflow when translated text expands | MEDIUM | After insertion, compare estimated cell text height vs row height; flag |
| **PDF layout complexity score** | Native PDFs with multi-column, rotated text, embedded tables are risky; surface this before translation starts | MEDIUM | PyMuPDF block analysis: count columns, detect rotated spans, count tables; return complexity = low/medium/high with explanation |

#### D4: Review UX

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Side-by-side source / translation view** | Core differentiator vs commodity download-only; reviewers see quality immediately | MEDIUM | Split pane: left = source segments, right = editable translated segments; aligned by segment index |
| **Inline edit of translated segments** | Reviewer can fix a sentence in place before export | MEDIUM | Contenteditable spans or textarea-per-segment; save on blur; re-aggregate on export |
| **Segment-level status (pending / translated / edited / approved)** | Provides workflow clarity; shows which segments have been reviewed | LOW | Per-segment state in frontend; persist to backend on save |
| **Re-translate individual segment** | Reviewer can ask LLM to redo one segment with optional instruction | MEDIUM | Single-segment POST endpoint; show diff vs original LLM output |
| **Export after editing** | Download the final file with reviewer's edits baked in | MEDIUM | Backend regenerates the output file using edited segment map; replaces original translated content |
| **Glossary hit markers in review pane** | Signals which terms were enforced; builds confidence in the PoC | LOW-MEDIUM | CSS highlight class on glossary-matched spans |

### Nice-to-Have Differentiators (Build If Time Allows — Do Not Block Demo)

| Feature | Value Proposition | Complexity | Build? |
|---------|-------------------|------------|--------|
| **Alternative translation suggestions** | Show 2–3 LLM alternatives for a segment; reviewer picks | HIGH | Skip — time risk |
| **Back-translate (translate back to source for QA)** | Quality check: does retranslation match original? | HIGH | Skip — interesting but not demo-critical |
| **Bilingual output PDF** | Source + translation side-by-side in exported PDF (like PDFMathTranslate) | HIGH | Defer — compelling but complex PDF layout work |
| **Language direction swap** | Swap source/target quickly for re-use | LOW | Add if trivially available after language picker is built |
| **Per-segment quality score** | Show LLM confidence or COMET-style score per segment | HIGH | Skip — unreliable without a dedicated QA model |

---

## Anti-Features for PoC (Do NOT Build — Explicitly Deferred)

Features competitors have that would consume the entire 2–3 week timeline without advancing the demo.

| Anti-Feature | Why Tempting | Why to Avoid for PoC | What to Do Instead |
|--------------|--------------|----------------------|--------------------|
| **Translation memory (TM) / fuzzy matching** | All enterprise TMS tools have it; sounds essential | Requires a segment database, similarity search (embeddings or edit distance), match UI — minimum 1 week to do right | Glossary covers the "consistency" story; TM is a v2 add-on |
| **Multi-file / batch upload** | Useful for real workflows | Multiplies job orchestration complexity; PoC needs to nail single-file quality first | Demo uses one file at a time; show quality, not throughput |
| **Multi-tenant workspaces / projects** | Smartling, Phrase are built around this | Requires auth, RBAC, project namespacing — weeks of infra | PoC is single-team; everyone sees the same jobs list |
| **User authentication / login** | Expected in production tools | Adds session/JWT complexity with no demo benefit for an internal team | No auth; simple API key or open access for internal use |
| **Role-based approval chains** | Lilt, Smartling have translator → reviewer → PM workflows | Complex state machines; requires multi-user coordination | Side-by-side review with export is sufficient to show the concept |
| **Billing / usage metering** | All SaaS tools have it | Zero demo value; adds Stripe/payment complexity | Track cost in logs; report total tokens in job metadata as a proxy |
| **Full observability stack (Datadog, etc.)** | Production requirement | Not visible to AICore reviewers in demo | stdout logging + job status in DB is enough to debug during demo |
| **Translation quality scoring (COMET, BLEU)** | Sounds impressive | Requires reference translations or dedicated QA model; automated scores don't map to human judgment reliably | Human review UX (side-by-side + inline edit) is a stronger demo of quality than a number |
| **Custom fine-tuned model** | Ultimate quality differentiator | Requires training data curation + GPU time — weeks minimum | Qwen off-the-shelf with good prompting is the PoC story |
| **Mobile / responsive layout** | Nice for polished product | Demo is desktop internal tool; mobile adds CSS complexity | Desktop-first; 1280px viewport is fine for demo |
| **Real-time collaboration (multi-user edit)** | Phrase has it | WebSocket complexity; PoC reviewers will not edit simultaneously | Single-user review session; export and share the result |
| **Pixel-perfect scanned PDF reconstruction** | The ideal | OCR + layout reconstruction from images is research-level hard; risk of demo failure | Scanned PDF = readable text output (plain or overlay); explicitly set expectations |
| **Pixel-perfect PDF (complex multi-column)** | What reviewers imagine | Multi-column PDF layout reconstruction requires bounding-box reflow algorithms | Set scope: single-column/simple PDF = high fidelity; complex layouts get complexity warning |
| **XLSX support** | Common enterprise format | Spreadsheet cell semantics (formulas, named ranges, merged cells) require separate logic | Out of scope per PROJECT.md; DOCX/PDF/PPTX is the PoC story |

---

## Feature Dependencies

```
File Upload
    └──enables──> Format Detection
                      └──enables──> DOCX Pipeline
                      │                 └──requires──> Text Run Extraction
                      │                 └──requires──> Segment Batching
                      │                 └──requires──> Qwen LLM Call
                      │                 └──requires──> DOCX Reconstruction
                      │
                      └──enables──> Native PDF Pipeline
                      │                 └──requires──> PyMuPDF Layout Extraction
                      │                 └──requires──> Complexity Score
                      │                 └──requires──> Segment Batching
                      │                 └──requires──> Qwen LLM Call
                      │                 └──requires──> PDF Reconstruction
                      │
                      └──enables──> PPTX Pipeline
                                        └──requires──> python-pptx Text Extraction
                                        └──requires──> Segment Batching
                                        └──requires──> Qwen LLM Call
                                        └──requires──> Overflow Detection + Auto-scale
                                        └──requires──> PPTX Reconstruction

Glossary Upload (optional)
    └──enhances──> Qwen LLM Call (via prompt injection)
    └──enables──> Glossary Hit Detection (post-process)
    └──enables──> Glossary Markers in Review UI

Qwen LLM Call
    └──produces──> Translated Segment Store (in-memory or Redis)
    └──enables──> Review UI (segments available)

Review UI
    └──requires──> Translated Segment Store
    └──enables──> Inline Edit
    └──enables──> Segment Re-translate
    └──enables──> Export After Edit

Export After Edit
    └──requires──> Edited Segment Store
    └──requires──> Original Document Structure (preserved from pipeline)
    └──produces──> Final Translated File (download)

Auto-detect Source Language
    └──enhances──> Language Picker UX (pre-fills source)
    └──uses──> langdetect or Qwen identify call

Overflow Detection (PPTX)
    └──requires──> PPTX Reconstruction
    └──enables──> Overflow Warning in Review UI
```

### Critical Dependency Notes

- **Export After Edit requires Original Document Structure preserved.** The translation pipeline must not discard the parsed structure (XML tree for DOCX/PPTX, block coordinates for PDF) after initial translation — it needs to be available when the reviewer finalises edits. Store structure alongside segments.
- **Review UI requires a segment-addressable data model.** Every text unit must have a stable ID that maps source segment → translated segment → edited segment → position in output document. This ID scheme is the core data model decision and must be designed before the UI.
- **Glossary injection requires the glossary to be available at LLM call time.** If glossary upload and translation job are submitted together (single-step UX), they must be linked before the first segment call.
- **PDF Reconstruction is the highest-risk dependency.** It is the last step of the native PDF pipeline and the hardest to get right. All upstream work (extraction, translation) is wasted if reconstruction breaks layout. Prototype this first as a standalone spike.

---

## MVP Definition

### Launch With (PoC Demo — 2–3 weeks)

Minimum set to make the demo compelling. Each item maps to something AICore reviewers will actively check.

- [ ] **File upload + format detection** — entry point; must work for DOCX, native PDF, PPTX
- [ ] **DOCX translation with format preservation** — hero format; tables, styles, headers preserved
- [ ] **Native PDF translation with single-column fidelity** — hero format; complex layout gets warning
- [ ] **PPTX translation with overflow detection + basic auto-scale** — visual format bonus
- [ ] **Qwen LLM engine with segment batching and system prompt** — the quality differentiator
- [ ] **Glossary upload (CSV) with prompt-injection enforcement** — terminology control story
- [ ] **Side-by-side review UI with inline edit** — UX differentiator; no competitor has this in free tier
- [ ] **Export after edit (download in original format)** — closes the review loop
- [ ] **Translation progress indicator** — prevents "is it working?" anxiety during demo
- [ ] **Source auto-detect + target language picker** — basic usability; must be present

### Add After Validation (v1.x — post-demo if productizing)

- [ ] **Glossary hit highlighting** — once glossary enforcement is stable, add visual markers
- [ ] **Segment re-translate (single segment)** — once review UI is stable
- [ ] **Scanned PDF (OCR)** — PaddleOCR path; readable output only; not blocking demo
- [ ] **Language direction swap** — low-effort UX improvement
- [ ] **Bilingual output PDF** — compelling but medium complexity; good for v1.x

### Future Consideration (v2+ — productization)

- [ ] **Translation memory (TM)** — segment database + similarity search; weeks of work; not demo-critical
- [ ] **Multi-file batch upload** — throughput story; quality is the PoC story
- [ ] **Custom fine-tuned Qwen model** — after seeing quality gaps in production use
- [ ] **Multi-user review + real-time collaboration** — when multiple teams use the tool simultaneously
- [ ] **XLSX support** — when spreadsheet use cases emerge from real users
- [ ] **Multi-tenant auth / RBAC** — when moving from internal tool to product
- [ ] **Full observability + cost metering** — when productizing with multiple teams

---

## Feature Prioritization Matrix

| Feature | User Value (Demo) | Implementation Cost | Priority |
|---------|-------------------|---------------------|----------|
| DOCX translation + format preservation | HIGH | HIGH | P1 |
| Native PDF translation + layout fidelity | HIGH | HIGH | P1 |
| Qwen LLM with segment batching | HIGH | MEDIUM | P1 |
| File upload + format detection | HIGH | LOW | P1 |
| Side-by-side review UI | HIGH | MEDIUM | P1 |
| Inline edit + export | HIGH | MEDIUM | P1 |
| Glossary upload + prompt injection | HIGH | MEDIUM | P1 |
| Translation progress indicator | MEDIUM | LOW | P1 |
| Source auto-detect + target picker | MEDIUM | LOW | P1 |
| PPTX translation + overflow detection | MEDIUM | MEDIUM | P2 |
| Overflow warning in review UI | MEDIUM | LOW | P2 |
| Glossary hit highlighting | MEDIUM | MEDIUM | P2 |
| Segment re-translate | MEDIUM | MEDIUM | P2 |
| Scanned PDF (OCR, readable output) | LOW | HIGH | P2 |
| PDF complexity score + warning | MEDIUM | LOW | P2 |
| Language direction swap | LOW | LOW | P3 |
| Bilingual output PDF | LOW | HIGH | P3 |
| Alternative translation suggestions | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for demo (build in weeks 1–2)
- P2: Should have; add in week 3 if P1 is stable
- P3: Nice to have; defer to post-demo

---

## Per-Category Analysis

### 1. Document Ingestion

**Table stakes:** Single-file drag-drop upload, format detection from MIME type + extension, 50 MB size limit (covers real enterprise docs), clear error for unsupported formats.

**Differentiator (do not over-build):** Preview of parsed structure (page count, slide count, word count) gives reviewers confidence the tool understood the document.

**Anti-feature for PoC:** Batch upload, folder import, cloud storage connectors (Google Drive, SharePoint).

### 2. Language Selection

**Table stakes:** Target language dropdown (prioritise EN, VI, JA, ZH, KO), source auto-detect.

**Differentiator:** Quality hint badge ("Recommended pair" vs "Community-tested"). Direction swap button.

**Anti-feature for PoC:** Per-language quality statistics, language pair availability matrix.

### 3. Translation Engine

**Table stakes:** Correct translation of the document content in the target language.

**Differentiator:** Segment batching with sliding context window (beats single-segment commodity calls); system prompt with document type + domain context; Qwen model selection UI (`qwen-plus` vs `qwen-max`).

**Anti-feature for PoC:** Translation memory / fuzzy matching, BLEU/COMET scoring, model comparison mode.

### 4. Format Preservation

**Table stakes (per format):**
- DOCX: text runs, paragraph styles, tables, headers/footers, images (pass-through, not translate alt text in PoC)
- PDF: text positioned near original coordinates; images passed through; fonts substituted if not embeddable
- PPTX: text boxes, slide structure, images, speaker notes (flag but do not block)
- Scanned PDF: readable OCR output; side-by-side or overlay acceptable

**Differentiator:** Complexity score for PDF before translation; overflow detection for PPTX; explicit per-format capability table shown in UI ("What we preserve").

**Anti-feature for PoC:** Pixel-perfect scanned PDF reconstruction, XLSX, complex multi-column PDF reflow, right-to-left language layout reversal.

### 5. Glossary / Terminology

**Table stakes:** CSV/TSV upload with source→target columns; prompt injection per job.

**Differentiator:** Post-translation enforcement check (did the LLM honour the terms?); UI markers on segments where glossary terms were applied.

**Anti-feature for PoC:** Fuzzy glossary matching (e.g., "OpenAI" matching "Open AI"), shared glossary library across jobs, glossary versioning, conflict resolution rules.

### 6. Review & Edit UX

**Table stakes:** Side-by-side view (source on left, translation on right), visible segment boundaries.

**Differentiator:** Inline editable segments, segment status (translated / edited), re-translate single segment, glossary markers.

**Anti-feature for PoC:** Multi-user real-time collaboration, segment locking, formal approve/reject workflow, translation memory populated by edits, tracked changes (Word-style).

### 7. Export & Delivery

**Table stakes:** Download in original format (DOCX → DOCX, PDF → PDF, PPTX → PPTX) with reviewer edits applied.

**Differentiator:** Export from review state (not just initial output); show "n segments edited by reviewer" summary.

**Anti-feature for PoC:** Bilingual PDF (defer to v1.x), sharing links, email delivery, cloud storage upload.

### 8. Quality Feedback

**Differentiator (lightweight, affordable):** Per-segment "flag an issue" button that queues a re-translate with optional reviewer note; show alternative translations count.

**Anti-feature for PoC:** Per-segment automated quality score, QA report export, back-translate loop.

### 9. Admin / Observability

**Anti-feature for PoC:** Cost dashboard, per-user analytics, token usage by project, SLO alerts. Sufficient: job history list (last 20 jobs), job metadata (tokens used, time taken) in a simple table, stderr/stdout logging.

### 10. Security / Privacy

**Flag for AICore:** Qwen API routes through Alibaba Cloud (DashScope). If AICore has data-residency concerns about document content leaving the AICore network to Alibaba Cloud infrastructure, this must be raised before the PoC demo — not after. No on-prem option in PoC scope (Qwen is API-only). Mitigation: use test/synthetic documents in the demo; redact any sensitive content.

**Anti-feature for PoC:** Audit trail, document retention policies, end-to-end encryption at rest, on-prem Qwen (requires self-hosted model — significant infrastructure).

---

## Sources

- [Azure AI Translator Document Translation Overview](https://learn.microsoft.com/en-us/azure/ai-services/translator/document-translation/overview)
- [Azure Glossary Formats Reference](https://learn.microsoft.com/en-us/azure/ai-services/translator/document-translation/reference/get-supported-glossary-formats)
- [DeepL Document Translation Features](https://www.deepl.com/en/features/document-translation)
- [DeepL API Document Reference](https://developers.deepl.com/api-reference/document)
- [DeepL Glossary Features](https://www.deepl.com/en/features/glossary)
- [Google Translate — Translate Documents Help](https://support.google.com/translate/answer/2534559)
- [Smartling AI Translation Workflow](https://help.smartling.com/hc/en-us/articles/29184719093275-Setting-Up-a-Machine-or-LLM-Translation-Workflow)
- [Smartling Review Mode Overview](https://help.smartling.com/hc/en-us/articles/360024400634-Overview-of-Review-Mode)
- [Phrase (Memsource) Review — EHLION](https://ehlion.com/magazine/phrase-memsource-review/)
- [Intento Enterprise Language Hub](https://inten.to/enterprise-language-hub/)
- [PDFMathTranslate GitHub](https://github.com/PDFMathTranslate/PDFMathTranslate)
- [BabelDOC GitHub](https://github.com/funstory-ai/BabelDOC)
- [LibreTranslate GitHub](https://github.com/LibreTranslate/LibreTranslate)
- [python-pptx Auto-fit Text Analysis](https://python-pptx.readthedocs.io/en/latest/dev/analysis/txt-autofit-text.html)
- [Structured Document Translation via FormatRL — arXiv 2024](https://arxiv.org/html/2512.05100)
- [How LLMs Can Translate PDFs — Medium](https://medium.com/@turgutgvcn/how-llms-can-actually-translate-pdfs-layout-matters-f990b175b6e7)
- [Best AI Document Translation Tools 2025 — Bluente Blog](https://www.bluente.com/blog/ai-document-translation-tools)
- [WMT25 Terminology Translation Task Findings](https://aclanthology.org/2025.wmt-1.30.pdf)
- [Intento State of Translation Automation 2025](https://inten.to/the-state-of-translation-automation-2025/)

---
*Feature research for: AI document translation PoC (AICore internal demo)*
*Researched: 2026-04-17*
