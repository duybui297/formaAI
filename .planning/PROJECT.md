# AI Translation PoC

## What This Is

A web-based AI document translation PoC that takes office documents (DOCX, PDF, PPTX) in any language pair and returns translated versions that preserve the original format as closely as the format allows. Built as an internal demo for the **AICore** team (an AI-native startup) to evaluate whether Qwen-class LLMs plus layout-aware processing can beat commodity document translation tools (Azure Translator, DeepL, Google Docs translate) on quality, terminology control, and UX.

## Core Value

**Translate documents with format fidelity that makes the translated output usable as-is** — without forcing reviewers to re-create layouts. Everything else (UX polish, glossary features, multi-format scope) is secondary to this.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. Hypotheses until validated. -->

- [ ] Upload a document (DOCX, PDF, PPTX) and choose source + target language
- [ ] Translate using Qwen (DashScope API) with segment-level prompts
- [ ] Preserve format on the "hero" paths: DOCX (near pixel-perfect) and native PDF (high fidelity)
- [ ] Handle PPTX with layout-aware translation (text-box auto-fit, overflow flags)
- [ ] Handle scanned PDF via OCR with a readable output (side-by-side or overlay)
- [x] Custom glossary / terminology injection (company-specific terms enforced across the doc) — Phase 2
- [~] Smart layout handling: flag text expansion/overflow; auto-scale where safe — flagging done in Phase 2; auto-scale deferred to Phase 3
- [x] Side-by-side review UX: see source + translation, inline correct before export — Phase 2
- [ ] Download the translated file in the original format
- [ ] Multi-lingual (any pair the LLM supports — no hardcoded language list)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **XLSX support** — deferred to v2; demo doesn't hinge on spreadsheets
- **Pixel-perfect scanned-PDF reconstruction** — research-level hard; readable + side-by-side is the PoC bar
- **Multi-tenant auth / RBAC** — PoC is a single-team internal tool; defer until productization
- **Production-grade ops (observability, SLOs, rate-limit tiers)** — PoC scope; log + trace enough to debug
- **Translation memory / fuzzy-match reuse** — deferred; glossary covers the demo-critical terminology story
- **Human-translator marketplace / collaboration workflows** — out of PoC scope
- **Mobile app** — web only for the PoC
- **Custom fine-tuned models** — use Qwen off-the-shelf; fine-tuning is a v2 question once we see quality gaps

## Context

**Organizational:**
- Built at **AICore** (an AI-native startup) as an internal demo to evaluate AI doc-translation capability.
- PoC-first: the goal is a demo that wins AICore's confidence in 2–3 weeks, not a production launch.
- User (Thu, AI Engineer at AICore) has a strong Python/FastAPI, LangChain, LlamaIndex, Qdrant, Redis, RabbitMQ background from prior production RAG work to draw on.

**Technical landscape:**
- **Model:** `qwen-mt-turbo` — Alibaba's dedicated translation model on DashScope. (Research verified the user-provided name "qwen3.6-plus" does not exist in the live catalog; `qwen-mt-turbo` is the correct pick: 92 languages incl. Vietnamese, a native `terminology` API parameter for glossary injection, ~$0.49 / 1M output tokens.) Accessed via the **OpenAI-compatible endpoint** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` using the `openai` Python SDK — not the `dashscope` SDK. DashScope international vs China endpoints are separate accounts with non-portable keys; a Day-1 health check from the dev machine is required.
- **Formats:** OOXML (DOCX, PPTX) are structured XML — translate text runs in place. Native PDF needs layout-aware extraction (PyMuPDF / pdfplumber) and careful reinsertion. Scanned PDF needs OCR (candidates: PaddleOCR, Tesseract, Azure Document Intelligence, commercial APIs).
- **Commercial baseline to exceed:** Azure AI Translator's Document Translation API already preserves OOXML + PDF formatting and supports Vietnamese. "We wrapped Azure" is not a compelling demo — our angle is LLM quality + glossary control + layout intelligence + review UX.

**Known hard problems we will hit:**
- Text expansion (translations are often 20–40% longer than source; VN → JA can shrink, EN → VN can grow) will overflow PPTX text boxes and break PDF layouts.
- OCR quality on real-world scanned PDFs is the biggest risk factor for that format.
- Segment-level LLM calls lose document context (figures, cross-references); batching + context windows need design thought.
- Tables, lists, footnotes, speaker notes — each has its own OOXML quirks.

## Constraints

- **Timeline**: 2–3 weeks from kickoff to demo — drives aggressive scoping and "hero format first" prioritization.
- **Tech stack (model)**: `qwen-mt-turbo` on Alibaba DashScope (international endpoint), accessed via the `openai` Python SDK against the OpenAI-compatible base URL. Glossary uses the native `terminology` API parameter.
- **Tech stack (backend)**: Python / FastAPI assumed — matches Thu's existing production stack and keeps cognitive overhead low. Async patterns for long-running translation jobs.
- **Tech stack (frontend)**: Next.js (React) assumed — matches ICOM-P3 frontend; fastest path to a demo-quality UI.
- **Audience**: Internal AICore team. No external users, no data-residency contract — but Qwen API routes through Alibaba Cloud; flag if AICore has concerns about that.
- **Deployment**: Internal web app (docker-compose or single VM) is sufficient for the PoC demo.
- **Quality bar**: "Readable + high fidelity + pixel-perfect" was the user's stated aspiration — the realistic per-format bars are documented in `## Context` above. We will not promise pixel-perfect on scanned PDFs.
- **Languages**: Multi-lingual — pair is user-selected per job, not hardcoded. Vietnamese, English, Japanese, Chinese must all work well given AICore's target market.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `qwen-mt-turbo` (DashScope international, OpenAI-compatible endpoint) | Dedicated translation model with native `terminology` glossary API; 92 languages incl. Vietnamese; ~$0.49/1M output tokens | ✓ Good — verified against live catalog |
| DOCX + native PDF are the "hero" formats | Most common real-world docs; best fidelity achievable in PoC scope; PPTX is visual bonus | — Pending |
| Scanned PDF = "readable" bar only | Layout reconstruction from OCR is research-level; side-by-side or overlay is honest and still useful | — Pending |
| Build differentiators on top of a translation core: LLM quality + glossary + smart-layout + review UX | "We wrapped Azure" isn't a compelling demo; these four are what AICore will remember | — Pending |
| Web app (FastAPI + Next.js) over CLI / desktop | Demo-friendly; matches existing stack; easiest path to share links with AICore reviewers | — Pending |
| PoC: no auth, no multi-tenancy, minimal ops | 2–3 week timeline; internal-only demo; don't burn weeks on infrastructure we won't ship | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-17 after initialization*
