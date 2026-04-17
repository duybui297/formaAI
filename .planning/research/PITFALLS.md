# Pitfalls Research

**Domain:** AI document translation (DOCX, PPTX, native PDF, scanned PDF) with LLM (Qwen/DashScope)
**Researched:** 2026-04-17
**Confidence:** HIGH (domain-specific; patterns verified against library issues, official docs, and production reports)

---

## Top-10 Demo-Killers

A pre-demo checklist. If any of these are unresolved on demo day, the demo will visibly fail.

| # | Demo-Killer | Pre-Demo Check |
|---|-------------|----------------|
| 1 | **Silent content dropping** — LLM skips a paragraph or table cell entirely | Run a segment-count assertion: `assert len(translations) == len(source_segments)` |
| 2 | **DOCX run-splitting corruption** — naïve `run.text = translated` fractures mid-word formatting | Open output in Word; look for unstyled spans or split words |
| 3 | **PPTX text-box overflow** — translated text spills off slide edge; invisible in thumbnail | Check `shape.text_frame.auto_size` flag; run overflow detector on every shape |
| 4 | **DashScope wrong endpoint / 401** — using China endpoint from non-China IP (or vice versa) | `curl` the health endpoint with the demo API key 24 h before demo |
| 5 | **Vietnamese tone marks mangled** — NFD-encoded diacritics become question marks or split characters | Run `unicodedata.normalize('NFC', text)` in unit test with a known VN string |
| 6 | **Column-layout PDF scramble** — two-column paper extracted left-right instead of column-by-column | Include a two-column test PDF in the smoke test suite |
| 7 | **Demo doc triggers model refusal** — Qwen content filter blocks an innocuous slide | Pre-translate the exact demo doc a day before; never live-translate it for the first time on stage |
| 8 | **LLM adds commentary** — model prepends "Translated from English:" or explains its choices | Validate output with a starts-with-source-language check; enforce `output_format: translation_only` in system prompt |
| 9 | **File upload silently dropped** — browser or nginx hits a default 10 MB body limit | Set `client_max_body_size 50m` in nginx; validate with a 30 MB DOCX upload before demo |
| 10 | **No progress feedback = demo feels broken** — 2-minute job with a static spinner loses the audience | Wire up a WebSocket/SSE progress stream; show "Translating segment 12/47" minimally |

---

## Critical Pitfalls

### Pitfall 1: DOCX Run-Splitting — The Single Most Common DOCX Translation Bug

**What goes wrong:**
Word does not guarantee that a sentence is stored as one `<w:r>` run. Spell-check, auto-correct, tracked changes, and incremental edits fragment a single logical sentence across many runs with subtly different `<w:rPr>` style blocks. Naïve code like:

```python
for run in paragraph.runs:
    run.text = translate(run.text)
```

sends the LLM fragments like `"The product"`, `" is"`, `" available"` as separate translation units. Each fragment gets translated in isolation, producing incoherent output, broken compound words in German/Vietnamese, and duplicated articles.

**Why it happens:**
Word internally splits runs at spell-check boundaries, font-substitution boundaries, and wherever the user repositioned the cursor mid-word. The paragraph's logical text is only recoverable by concatenating all `run.text` values — but the run boundaries must be preserved for style reconstruction.

**How to avoid:**
1. Extract `paragraph.text` (the full logical text) and translate it as a unit.
2. Map translated text back onto the original runs proportionally, or collapse all runs in the paragraph to a single run carrying the first run's style, then set its text.
3. Preferred pattern: paragraph-level extraction → single-run reassembly preserving the first run's `rPr`.

**Warning signs:**
- Output DOCX has alternating bold/normal words with no pattern.
- Individual run texts are single words or partial words.
- LLM returns `"The"` / `"product"` as separate translation calls.

**Phase to address:** Phase 1 — DOCX extraction and reassembly core.

---

### Pitfall 2: Silent Segment Dropping by the LLM

**What goes wrong:**
When batching segments into a single LLM call (e.g., 30 paragraph texts as a JSON array), the model occasionally returns fewer items than sent. This is the most demo-killing bug: the translated DOCX is shorter than the source, with sections simply absent. No error is raised.

**Why it happens:**
The model treats a long JSON array as "fill in what's interesting" rather than a strict schema contract. Qwen models, like GPT-4, will occasionally merge two adjacent items, skip an empty-looking segment, or stop early near the context window limit.

**How to avoid:**
1. Always assert `len(response_items) == len(request_items)` after parsing.
2. Use numbered placeholders: `"[1] First sentence"` → `"[1] Translated"`. Detect missing numbers and retry only missing segments.
3. Set a hard maximum batch size (e.g., 20 segments, ~2000 tokens total) to stay safely inside context limits.
4. On assertion failure: retry the batch at half size; if still failing, translate segments individually.

**Warning signs:**
- Output document has fewer paragraphs than input.
- Translated JSON array length does not equal input array length.
- Specific heading or section is absent from output.

**Phase to address:** Phase 2 — LLM translation pipeline with batch orchestration.

---

### Pitfall 3: LLM Adding Unsolicited Content

**What goes wrong:**
The model prepends or appends text that was not in the source: `"Translated from English:"`, `"Note: The following is a machine translation"`, explanatory parentheticals, or footnote-style commentary. In a PPTX slide this is immediately visible and looks broken.

**Why it happens:**
The system prompt doesn't sufficiently constrain the output format. Models, especially instruction-tuned ones, default to "being helpful" by annotating their work.

**How to avoid:**
1. System prompt must be explicit: `"Return ONLY the translated text. No explanations, no prefixes, no meta-commentary."`
2. Validate output with a simple heuristic: if the response starts with a language tag or contains phrases like "Translation:", "Note:", "原文:", reject and retry with a stricter prompt.
3. For structured batch output (JSON), validate schema strictly; extra keys are a red flag.

**Warning signs:**
- Translation output is significantly longer than statistically expected (e.g., EN→VN grows 30%, but output is 200% longer).
- Output contains colons followed by the word "translation" in any language.

**Phase to address:** Phase 2 — LLM translation pipeline; Phase 3 — output validation layer.

---

### Pitfall 4: DashScope Endpoint / Region Mismatch

**What goes wrong:**
DashScope has separate API endpoints and account systems for China mainland (`dashscope.aliyuncs.com`) vs. international (`dashscope-intl.aliyuncs.com`, Singapore; `dashscope-us.aliyuncs.com`, US Virginia). API keys are not interchangeable across regions. Calling the China endpoint from Vietnam returns a 401 with no helpful message. The wrong model name on the international endpoint returns 404 — newer models like `qwen3-*` may only be available on specific regional endpoints.

**Why it happens:**
Alibaba Cloud's documentation defaults to China examples. Engineers copy the endpoint from Chinese tutorials without noticing the regional suffix.

**How to avoid:**
1. Use `dashscope-intl.aliyuncs.com` (Singapore) for this project — lowest latency from Vietnam.
2. Store the base URL in env config, never hardcode.
3. Verify the exact model name against the international model catalog before building the pipeline — `qwen-plus`, `qwen-max`, `qwen-mt-plus` are confirmed on the international endpoint; `qwen3.6-plus` needs explicit verification.
4. Implement a `/health` check endpoint in the app that makes a minimal DashScope call on startup and logs the endpoint in use.

**Warning signs:**
- 401 errors despite correct API key.
- 404 for a model that appears in documentation.
- Response latency is unexpectedly high (>10s for a short prompt) — may indicate geo-routing to the wrong region.

**Phase to address:** Phase 1 — infrastructure setup; verify on Day 1 before any pipeline work.

---

### Pitfall 5: PPTX Text-Box Overflow After Translation

**What goes wrong:**
Vietnamese translated from English is typically 20–40% longer. PPTX shapes have fixed dimensions. When translated text exceeds the shape bounds, PowerPoint silently clips the overflow — it is invisible in the python-pptx object model (no exception) but visible when the file is opened in PowerPoint or exported to PDF. The demo slide literally has text missing from the bottom.

**Why it happens:**
python-pptx's `auto_size` property reads the OOXML `<a:bodyPr autofit>` attribute, but many real-world slides were authored with `autofit=OFF` to lock the layout. The library does not simulate the text renderer — it cannot know if text overflows without a font metrics engine.

**How to avoid:**
1. After reassembling translated text into shapes, run a heuristic overflow detector: estimate character width × font size × line count vs. shape height.
2. If overflow detected: (a) reduce font size via `shape.text_frame.fit_text()`; (b) flag the shape in the review UI with a visual warning badge; (c) never silently truncate.
3. For the demo, pre-select slides where text expansion is manageable (<25%); have an "overflow flags" panel in the review UI.
4. Set `text_frame.word_wrap = True` before measuring — unwrapped text overflows immediately.

**Warning signs:**
- Translated text has more characters than source on slides with small text boxes.
- Font size in translated shape is smaller than source (auto-scaling may have fired silently).
- Shape bounding box has the same height as the source but more content.

**Phase to address:** Phase 3 — PPTX layout handling and overflow detection.

---

### Pitfall 6: PDF Column-Layout Reading Order Scramble

**What goes wrong:**
PyMuPDF's default `page.get_text("text")` sorts text by vertical position (top-to-bottom), not by reading order. A two-column academic paper or business report gets extracted with line 1 of column A, then line 1 of column B, then line 2 of column A — interleaving content from both columns. When translated, the output is semantically nonsensical.

**Why it happens:**
PDF has no concept of "columns" in its page model. Text spans are positioned absolutely. `sort=True` in PyMuPDF sorts by y-coordinate, which is correct for single-column but wrong for multi-column layouts.

**How to avoid:**
1. Use `page.get_text("blocks")` to get bounding boxes, then cluster blocks into columns by their x-coordinate range before concatenating text.
2. PyMuPDF's `get_text("words")` with `sort=True` then regroup by column boundary is the standard approach.
3. PyMuPDF-Layout library (from the pymupdf org) provides a higher-level multi-column detection — use it for documents where multi-column is likely.
4. In the test suite, include a two-column PDF and assert that column 1 appears entirely before column 2 in the extracted text.

**Warning signs:**
- Extracted text from a known two-column doc interleaves sentences from different topics.
- Sentences start with a subject from one paragraph and end with a predicate from an unrelated one.
- `page.get_text("blocks")` shows blocks with alternating x-offsets near 0 and ~300.

**Phase to address:** Phase 2 — PDF extraction pipeline.

---

### Pitfall 7: Vietnamese Unicode Normalization (NFC vs NFD)

**What goes wrong:**
Vietnamese tone marks (e.g., `ắ`, `ổ`, `ề`) can be stored as a single precomposed Unicode codepoint (NFC, U+1EAF) or as a base letter plus combining accent (NFD, two codepoints). They look identical on screen but Python considers them different strings. When the LLM returns NFD-form text and the app renders it into a DOCX without normalizing, some fonts substitute unknown glyphs with boxes or question marks. PDF reinsertion fails silently for NFD forms on fonts that only carry NFC glyphs. String matching in glossary enforcement breaks.

**Why it happens:**
Qwen models, like most LLMs, may return either form depending on what was in training data. macOS file system uses NFD; Linux uses NFC; Windows uses NFC. Mixing origins produces mixed encodings.

**How to avoid:**
1. Always normalize LLM output to NFC immediately after receiving it: `text = unicodedata.normalize('NFC', text)`.
2. Also normalize all input text before sending to the LLM, and all glossary terms at load time.
3. Add a unit test: `assert normalize('NFC', llm_output) == normalize('NFC', expected)` — never compare raw strings for Vietnamese content.
4. In the review UI, ensure the font stack includes `Noto Serif` or `Times New Roman` — both carry full Vietnamese glyph sets.

**Warning signs:**
- Vietnamese text appears correct in the Python repr but shows boxes/question marks when opened in Word or a browser.
- `len("ắ") == 2` when it should be 1 (NFD form detected).
- Glossary term matching fails despite visually identical strings.

**Phase to address:** Phase 1 — text processing utilities (normalize at I/O boundary); Phase 2 — LLM response post-processing.

---

### Pitfall 8: Tracked Changes / Revision Marks Hiding Text from python-docx

**What goes wrong:**
DOCX files with unaccepted tracked changes store pending insertions in `<w:ins>` elements and pending deletions in `<w:del>` elements. `python-docx` walks the paragraph tree looking for `<w:r>` runs, but `<w:ins><w:r>...</w:r></w:ins>` is one level deeper than it looks for. The result: inserted text is silently skipped; deleted text (which the author intended to remove) is included. The translated document may contain deleted content and miss inserted content — a legally meaningful error if the document is a contract or policy.

**Why it happens:**
`python-docx` does not implement a "accept all changes" step before traversal. Most translation tools assume clean DOCX input.

**How to avoid:**
1. Pre-process DOCX input: accept all tracked changes before parsing. Use `python-docx`'s raw XML access (`doc._element`) to find and resolve `<w:ins>` / `<w:del>` nodes before traversal, or use `docx-revisions` library.
2. Alternatively, warn the user in the UI: "This document contains tracked changes. They will be accepted before translation. Please review the accepted version first."
3. Add a pre-flight check: scan for `<w:ins>` or `<w:del>` in the raw XML and surface a warning badge in the upload UX.

**Warning signs:**
- Output DOCX is shorter than expected despite the source having visible content.
- Source document was shared with track-changes enabled (common in Vietnamese enterprise Word usage).
- `doc._element.xml` contains `w:ins` or `w:del` strings.

**Phase to address:** Phase 1 — DOCX pre-processing and validation step.

---

### Pitfall 9: SmartArt and Grouped Shapes in PPTX — Text Silently Missed

**What goes wrong:**
`python-pptx` does not support SmartArt extraction. SmartArt objects (`<p:graphicFrame>` with `<a:graphicData uri="...smartArt...">`) appear in the slide's shape tree, but iterating `slide.shapes` and calling `shape.text_frame` throws an `AttributeError` or returns empty. Process diagrams, org charts, and timeline SmartArt — common in Vietnamese corporate PPTX decks — are silently untranslated.

Grouped shapes (`<p:grpSp>`) have a similar issue: `python-pptx` exposes the group but not the child shapes inside it unless you recurse into `group.shapes`.

**Why it happens:**
`python-pptx` explicitly does not implement SmartArt (noted as out of scope in the library docs). Shape iteration in `slide.shapes` does not automatically recurse into groups.

**How to avoid:**
1. SmartArt: detect `<p:graphicFrame>` elements whose graphic URI contains the SmartArt namespace. Flag them in the review UI as "manual translation required" rather than silently skipping.
2. Grouped shapes: write a recursive shape walker that descends into `<p:grpSp>` elements.
3. Use Aspose.Slides or Spire.Presentation (commercial) if SmartArt translation coverage is required; for the PoC, explicit flagging is sufficient.
4. Add a test PPTX fixture containing a SmartArt shape and assert the app raises a "manual review required" flag rather than silently ignoring it.

**Warning signs:**
- PPTX with org-chart or timeline slides has zero flagged shapes but also zero translated text on those slides.
- `isinstance(shape, pptx.shapes.graphfrm.GraphicFrame)` is true but `shape.has_text_frame` is false.
- A translated PPTX is missing content that was clearly visible in the source.

**Phase to address:** Phase 3 — PPTX shape extraction and audit.

---

### Pitfall 10: OCR Garbage-In, Garbage-Translation

**What goes wrong:**
When a scanned PDF has low resolution (<150 DPI), skew >5°, or heavy noise, OCR (PaddleOCR or Tesseract) produces garbled text. The LLM then faithfully "translates" the garbage, producing output that looks like meaningful text but is semantically random. This is worse than leaving the source untranslated because it destroys the signal while appearing correct at a glance.

**Why it happens:**
The LLM has no awareness that its input is OCR garbage. It will generate fluent target-language text even from nonsense input — hallucinating meaning to fill the context.

**How to avoid:**
1. Use OCR confidence scores as a gate. PaddleOCR returns a `score` per text box. Aggregate: if mean confidence < 0.7 for a page, flag the page as "low-confidence OCR — manual review required" instead of translating.
2. Do not auto-translate pages below the confidence threshold — surface them in the review UI with the raw OCR text visible.
3. Apply image pre-processing before OCR: deskew (OpenCV `deskew`), denoise, upscale to 300 DPI minimum.
4. For the demo: curate test scanned PDFs with known quality; do not run the demo with a live scan of unknown quality.

**Warning signs:**
- OCR output contains random character sequences with no word boundaries.
- PaddleOCR `drop_score` filtering removes >30% of detected boxes.
- The translated output contains "words" that are not in any dictionary.

**Phase to address:** Phase 4 — OCR pipeline for scanned PDF.

---

### Pitfall 11: Hyperlinks and Non-Translatable Content Translated by LLM

**What goes wrong:**
The LLM "helpfully" translates URLs, email addresses, code snippets, variable names (`{{username}}`, `{company_name}`), and template placeholders. A DOCX with the hyperlink `https://example.com/products` becomes `https://example.com/sản-phẩm` in the output, breaking the link. Template variables like `{{first_name}}` become `{{tên_đệm}}` — breaking downstream rendering.

**Why it happens:**
Without explicit instruction, the model treats the entire segment as translatable text. It has learned that these strings often have meaning and will apply semantic translation.

**How to avoid:**
1. Before sending to the LLM: extract URLs, emails, code blocks, and `{{...}}` templates. Replace with stable placeholder tokens: `[LINK_1]`, `[EMAIL_1]`, `[VAR_1]`.
2. After receiving the translation: restore placeholders. Assert all placeholder tokens are present in the output before substitution.
3. System prompt: `"Do not translate text inside square brackets []. These are placeholders that must appear verbatim in your output."`
4. Validate: `re.findall(r'\[LINK_\d+\]', translation)` must equal source count.

**Warning signs:**
- Translated DOCX has broken hyperlinks (URLs contain target-language characters).
- Template placeholders in the output differ from those in the source.
- LLM output has fewer `[PLACEHOLDER]` tokens than were injected.

**Phase to address:** Phase 2 — segment pre/post-processing layer (placeholder extraction and restoration).

---

### Pitfall 12: Glossary Terms Not Respected Despite Injection

**What goes wrong:**
Even with a glossary injected in the system prompt (`"Always translate 'AICore' as 'AICore'"`, `"Translate 'RAG' as 'Hệ thống RAG'")`), the LLM sporadically ignores glossary constraints — especially for terms that look translatable in context, multi-word terms, or terms that appear in idioms.

**Why it happens:**
The LLM treats the glossary as a soft preference, not a hard rule. Under distribution shift (e.g., the term appears in an unusual syntactic position), the model's in-context learning weight for the glossary instruction loses to the prior from pretraining.

**How to avoid:**
1. Post-processing enforcement: after receiving the translation, scan for each glossary source term in the original and verify the corresponding target term appears in the translation. If not, apply string replacement as a last resort.
2. For high-criticality terms (brand names, product names): always use post-processing replacement, not just prompt injection.
3. Keep glossaries small for the demo (5–10 terms) — larger glossaries dilute the instruction signal.
4. Use few-shot examples in the prompt for critical terms: `"Example: 'AICore team' → 'nhóm AICore'"`.

**Warning signs:**
- QA check shows brand names or product names translated inconsistently across a 50-page document.
- The same term appears differently in different paragraphs.
- Glossary has >20 entries — risk of prompt dilution increases.

**Phase to address:** Phase 2 — glossary injection; Phase 3 — post-processing validation and enforcement.

---

### Pitfall 13: PDF Font Embedding — Missing Glyphs for Vietnamese/CJK on Reinsertion

**What goes wrong:**
When reinserting translated text into a native PDF (e.g., using PyMuPDF's `page.insert_text()` or a reportlab overlay), the PDF must embed a font that carries the target language's glyphs. If the original PDF used a Latin-only font (e.g., Times New Roman subset) and the translation is Vietnamese (with tone marks) or CJK, the inserted glyphs render as empty boxes ("tofu"). This is silent — no error, just invisible characters.

**Why it happens:**
PDF font embedding is per-glyph subset. The original PDF's font resource only contains glyphs used in the source language. The rendering engine cannot display codepoints for which no glyph outline is embedded.

**How to avoid:**
1. Never reuse the source PDF's fonts for target-language text injection. Always embed a full font that supports the target language.
2. For Vietnamese: embed Noto Serif or Times New Roman (full, not subset). For CJK: embed Noto Sans CJK or Source Han Sans.
3. In PyMuPDF: use `page.insert_text(..., fontname="F1", fontfile="NotoSerif.ttf")` with an explicitly provided font file.
4. For native PDF, the "overlay" approach (place translated text over redacted source) is safer than in-place editing for the PoC.

**Warning signs:**
- Translated PDF opens in Adobe Reader; target-language characters are squares.
- `PyMuPDF` `insert_text` call does not raise an error but text is invisible.
- Source PDF's embedded font name does not contain "CJK", "Noto", or the target language.

**Phase to address:** Phase 2 — native PDF reconstruction layer.

---

### Pitfall 14: Async Job — No Progress Visibility

**What goes wrong:**
Translating a 40-page DOCX takes 2–4 minutes. With only a spinner, users (and the demo audience) assume the app has hung. In a demo setting, 30 seconds of silence is enough for someone to ask "is it stuck?" — which derails the narrative.

**Why it happens:**
Developers test with short documents; the job completes before the UX gap matters. Progress reporting is added "later" and never gets there.

**How to avoid:**
1. Implement a Server-Sent Events (SSE) or WebSocket progress stream from Day 1 of the pipeline.
2. Emit progress at natural checkpoints: document parsed, segment N/M translated, output assembled.
3. The frontend must show: current operation, segment count progress, and estimated time remaining (even a rough estimate).
4. Never leave the user staring at a static spinner for more than 5 seconds.

**Warning signs:**
- Test with a 30-page document — if the UI shows nothing for >10 seconds, progress is missing.
- Backend logs show segment completions but the frontend has no state change.

**Phase to address:** Phase 2 — async job infrastructure; wire progress before any end-to-end test.

---

### Pitfall 15: Segment ID Drift Between Translation and Review

**What goes wrong:**
The review UI shows a side-by-side view of source and translated segments. Segment IDs are assigned at parse time. If the user re-runs translation on a modified document (or if the pipeline re-parses), segment IDs shift. Edits made to segment 15 in the review UI are applied to what was segment 15 at edit time — but is now segment 17 after re-parse. The edit is silently applied to the wrong segment.

**Why it happens:**
Segment IDs are positional (index-based) rather than content-hash-based. Any insertion or deletion before a segment shifts all subsequent IDs.

**How to avoid:**
1. Assign segment IDs as content hashes (SHA-256 of the source text + position context), not array indices.
2. On re-translation, match existing edits by hash, not by position. Unmatched edits (source text changed) should be surfaced as "review required" rather than silently discarded.
3. The export step must pull translated text from the edit store keyed by hash, not by position.

**Warning signs:**
- Manual edit to one segment appears in a different segment in the exported document.
- After re-running translation on a modified doc, all segment positions in the UI shift by one.

**Phase to address:** Phase 4 — review UI and edit persistence design.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Translate run-by-run without merging | Faster to implement | Fragmented output, broken formatting | Never — fix before first demo |
| Skip segment-count assertion | Simpler batch logic | Silent content dropping on demo day | Never |
| Hardcode Chinese DashScope endpoint | Copy-paste from tutorial | 401 errors from Vietnam | Never |
| NFC normalization only in test utilities, not production path | Passes unit tests | Intermittent boxes/question marks in output | Never for VN-target translation |
| In-memory job state (no persistence) | No DB setup | Can't resume after crash; no progress on page refresh | Acceptable for PoC if job < 5 min |
| Positional segment IDs | Simpler data model | Edit drift on re-translation | Acceptable for PoC if re-translation is disabled in review mode |
| Single-size batch (no adaptive retry) | Simpler pipeline | Context overrun on long paragraphs | Unacceptable — must have retry |
| No placeholder protection | Faster prompt construction | Broken URLs and template variables in output | Never for any production-bound demo |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| DashScope / Qwen | Using China endpoint (`dashscope.aliyuncs.com`) from Vietnam | Use international endpoint (`dashscope-intl.aliyuncs.com`); store in env var |
| DashScope / Qwen | Assuming model names are stable across regions | Verify `qwen-plus`, `qwen-max`, `qwen-mt-plus` on international catalog before sprint starts |
| DashScope / Qwen | No retry on 429 (rate limit) | Implement exponential backoff with jitter; free tier is 3–10 RPM depending on model |
| python-docx | Iterating `paragraph.runs` directly for translation | Concatenate to `paragraph.text`, translate, reassemble into single run |
| python-docx | Assuming all text is in `body.paragraphs` | Check headers, footers, footnotes, endnotes, text boxes — all have separate paragraph trees |
| python-pptx | Iterating `slide.shapes` for all text | Recurse into group shapes; flag SmartArt as untranslatable |
| PyMuPDF | `page.get_text("text")` with `sort=True` for multi-column | Cluster blocks by x-coordinate range before concatenating |
| PyMuPDF | Reinserting text using source PDF's font | Always embed a target-language-capable font explicitly |
| PaddleOCR | Default `drop_score=0.5` passing garbage | Gate on aggregate page confidence; pre-process with deskew + 300 DPI upscale |
| FastAPI | Default 2 MB request body limit | Set `client_max_body_size` in nginx and `--limit-concurrency` in uvicorn; test with 30 MB file |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| One LLM call per segment (no batching) | 10-min translation for 200 segments; 429 rate limits | Batch 10–20 segments per call with numbered placeholders | Immediately at >50 segments |
| Synchronous LLM calls in FastAPI route handler | Request timeout; worker thread blocked | Use async background task + SSE for progress | At first >30-second document |
| Loading entire PDF into memory before streaming | OOM crash on 100 MB scanned PDF | Stream page-by-page; process one page at a time | At ~50 MB with default uvicorn config |
| Re-OCR on every re-translation | 60-second OCR repeated for every retry | Cache OCR results by file hash; only OCR once per upload | First retry of any scanned PDF |
| No connection pooling for DashScope HTTP | TCP handshake overhead on every call | Use `httpx.AsyncClient` as a long-lived instance; reuse across requests | At >5 concurrent translation jobs |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Static spinner on 2-minute job | User refreshes page, losing job | SSE progress stream showing segment-level progress |
| No cancel button | User uploads wrong file; has to wait 3 minutes | Implement job cancellation via a cancel token that aborts the async task |
| File size limit surprise after upload starts | User uploads 80 MB PPTX; error appears after 30s | Show file size limit in the upload UI before the user selects a file |
| Browser timeout on large download | Translated 200-page DOCX download fails at 120s | Stream the file download with chunked transfer; set `Content-Disposition` correctly |
| Review UI has no "regenerate segment" | Bad translation requires full re-run | Add per-segment "regenerate" button that calls the LLM on that segment alone |
| No overflow warning on PPTX shapes | Exported PPTX has text cut off; user discovers in PowerPoint | Show overflow badge on flagged shapes in review UI before export |

---

## "Looks Done But Isn't" Checklist

- [ ] **DOCX translation:** Looks correct in python-docx repr but verify in Word — run merging may have silently broken bold/italic at paragraph boundaries.
- [ ] **PPTX overflow detection:** Pipeline reports "0 overflow shapes" but slides must be visually inspected in PowerPoint or LibreOffice — the heuristic is not a renderer.
- [ ] **Glossary enforcement:** The LLM acknowledged the glossary in training but verify term consistency by scanning the output for each glossary source term and asserting the target term is present.
- [ ] **Scanned PDF OCR confidence:** PaddleOCR returned text but check the mean page confidence score — >0.7 is the minimum before translation should proceed.
- [ ] **Segment count parity:** Batch returned successfully but assert `len(translations) == len(source_segments)` — the LLM may have merged or skipped.
- [ ] **Vietnamese NFC normalization:** Translated text renders correctly in the review UI but assert `text == unicodedata.normalize('NFC', text)` in the post-processing test.
- [ ] **DashScope endpoint:** API calls succeed in local dev but verify the endpoint env var is set correctly in the Docker container on the demo machine.
- [ ] **Placeholder restoration:** Translation completed but assert all `[LINK_N]` and `[VAR_N]` tokens from the source appear verbatim in the output before substitution.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Silent segment dropping discovered post-demo | HIGH | Add `assert len` check; rebuild batch pipeline with numbered placeholders; re-translate all test docs |
| Run-splitting corruption already in demo doc | MEDIUM | Write paragraph-level merge utility; apply to existing output; re-export; validate in Word |
| DashScope 401 on demo day | HIGH | Pre-test endpoint 24h before; have a cached pre-translated backup doc ready to switch to |
| PPTX overflow discovered in exported file | MEDIUM | Add `fit_text()` call to all shapes; flag overflows in UI; re-export the affected PPTX |
| VN characters appear as boxes in PDF output | MEDIUM | Switch to font-embedding approach with Noto Serif; re-render affected pages only |
| OCR garbage translated as fluent text | HIGH | Add confidence gate; flag low-confidence pages; for demo, use pre-OCR'd test docs only |
| Glossary enforcement failure in demo | LOW | Apply post-processing string replacement for critical brand terms; takes <1 hour to implement |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| DOCX run-splitting corruption | Phase 1: DOCX extraction core | Open output in Word; check bold/italic/font consistency |
| Tracked changes hiding text | Phase 1: DOCX pre-processing | Test with a DOCX that has unaccepted tracked changes |
| Vietnamese NFC normalization | Phase 1: text processing utilities | Unit test with known VN string in NFD form |
| DashScope endpoint/region | Phase 1: infrastructure setup | `curl` health check from the demo machine |
| Silent segment dropping | Phase 2: LLM batch orchestration | Assert segment count before/after every batch call |
| LLM adding content | Phase 2: LLM output validation | Check output starts with translation, not commentary |
| Placeholder protection | Phase 2: segment pre/post-processing | Assert all `[TOKEN]` patterns round-trip correctly |
| Glossary enforcement | Phase 2: glossary injection + Phase 3: post-processing | Scan output for each glossary term; spot-check 10 occurrences |
| PDF column-layout scramble | Phase 2: PDF extraction pipeline | Test with a two-column PDF fixture |
| PDF font embedding | Phase 2: PDF reconstruction | Open translated PDF; check Vietnamese/CJK glyphs render |
| PPTX text-box overflow | Phase 3: PPTX layout handling | Run heuristic overflow detector; validate visually in PowerPoint |
| SmartArt not extracted | Phase 3: PPTX shape audit | Test with SmartArt PPTX; assert flagging fires |
| OCR garbage-in | Phase 4: OCR pipeline | Test with a low-resolution scan; assert confidence gate fires |
| Async job no progress | Phase 2: async job infrastructure | Time a 30-page doc; assert UI updates within 5 seconds |
| Segment ID drift on re-translation | Phase 4: review UI + edit persistence | Edit segment 5; re-translate; assert edit still applies to segment 5's content |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| DOCX extraction | Run-splitting; tracked changes hidden text | Merge paragraph runs before sending; accept all changes first |
| PDF extraction | Column layout scramble; font glyph assumptions | Block-based extraction with column clustering; always embed target font |
| LLM batch translation | Segment dropping; content addition; rate limits | Numbered placeholders; count assertion; exponential backoff |
| OCR for scanned PDFs | Garbage text translated as fluent output | Confidence gate at 0.7; image pre-processing (deskew, 300 DPI) |
| PPTX reconstruction | Text-box overflow; SmartArt silent skip | Overflow heuristic + flag; recursive group walker; SmartArt detection |
| Glossary enforcement | LLM ignores low-frequency terms | Post-processing replacement for brand names; few-shot examples |
| Review UI | Segment ID drift; edits not surviving re-export | Content-hash IDs; edit store keyed by hash not position |
| Demo day | Model refusal; wrong endpoint; no backup | Pre-translate demo doc 24h before; health check on startup; have cached fallback |

---

## Sources

- [python-docx Issue #340: Track changes not supported](https://github.com/python-openxml/python-docx/issues/340)
- [python-docx Issue #519: Splitting a run](https://github.com/python-openxml/python-docx/issues/519)
- [python-docx Issue #910: Combine runs of a paragraph](https://github.com/python-openxml/python-docx/issues/910)
- [Unstructured Issue #1821: DOCX text nested in revision-marks skipped](https://github.com/Unstructured-IO/unstructured/issues/1821)
- [python-pptx Issue #969: Shrink text on overflow](https://github.com/scanny/python-pptx/issues/969)
- [python-pptx Issue #448: GraphicFrame / SmartArt not supported](https://github.com/scanny/python-pptx/issues/448)
- [PyMuPDF MuPDF Forum: Double column PDF wrong reading order](https://forum.mupdf.com/t/bug-double-column-pdfs-text-extracted-in-wrong-order/265)
- [PyMuPDF Discussion #2396: Incorrect reading order on page transition](https://github.com/pymupdf/PyMuPDF/discussions/2396)
- [Alibaba Cloud Model Studio: Rate Limits by Model](https://www.alibabacloud.com/help/en/model-studio/rate-limit)
- [DashScope international endpoint 401 fix](https://github.com/QwenLM/Qwen-Image/issues/106)
- [Qwen3.6 Plus international API access](https://github.com/QwenLM/Qwen3/issues/1838)
- [LiteLLM DashScope integration docs](https://docs.litellm.ai/docs/providers/dashscope)
- [Python unicodedata: Unicode normalization](https://docs.python.org/3/library/unicodedata.html)
- [Unicode UAX #15: Normalization Forms](https://unicode.org/reports/tr15/)
- [LLM Hallucination Index 2026 (AnalyticsInsight)](https://www.analyticsinsight.net/llm/llm-translation-hallucination-index-2026-which-models-add-drop-or-rewrite-meaning-most-ranked)
- [PaddleOCR 3.0 Technical Report](https://arxiv.org/html/2507.05595v1)
- [PowerPoint Translation Guide — PPTX skill gist](https://gist.github.com/vlad-ds/9d2982583a8181729721fecd0bb45a20)
- docx-revisions library: https://github.com/balalofernandez/docx-revisions

---
*Pitfalls research for: AI document translation PoC (DOCX, PPTX, PDF, scanned PDF) with Qwen/DashScope*
*Researched: 2026-04-17*
