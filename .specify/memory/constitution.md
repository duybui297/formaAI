# AI Translation PoC Constitution

> Governing principles for the AI Translation PoC.
> This document supersedes ad-hoc conventions; any deviation must be
> justified in a PR description and, if persistent, captured as an ADR
> in `docs/decisions/`.

## Core Principles

### I. Format Fidelity First (NON-NEGOTIABLE)

The core value of this PoC is *translated documents usable as-is, without
forcing reviewers to re-create layouts*. UX polish, glossary depth,
multi-format breadth — all secondary to format fidelity on the hero paths
(DOCX, native PDF, PPTX).

**Operational rule:** features that improve UX at the cost of measurable
layout regression on the hero paths are rejected by default. Any layout
regression in a PR must be flagged in the PR description and signed off
by the maintainer.

### II. Eval-Driven for Model Code, TDD for Deterministic Code

Translation prompts, glossary application, segment batching, and OCR
post-processing are non-deterministic — `/speckit.tasks` and reviewers
must require an **eval delta** before merging changes to them.

- Deterministic code (parsers, reassemblers, API routes, DB models) → TDD
  via `pytest` red-green-refactor.
- Model-touching code → eval-first loop:
  1. Write or extend eval (input set + scoring function + target threshold).
  2. Run baseline. Record number.
  3. Make the change.
  4. Re-run eval. Compare.
  5. Only commit if the metric you care about went up or held.

**Never change a prompt without an eval delta.** This is the brownfield AI sin.

### III. Native Tool over Custom Path

When a vendor or library exposes the capability natively, prefer it over
a hand-rolled equivalent. This compounds: native paths are tested by the
upstream community and tend to age better.

Examples baked into current code (with ADRs):
- `qwen-mt-turbo` `terminology` parameter over prompt-level glossary
  injection ([ADR-0001](../../docs/decisions/0001-qwen-mt-turbo.md))
- PyMuPDF redact-and-reinsert over `pdf2docx` round-trip
  ([ADR-0003](../../docs/decisions/0003-pymupdf-direct-reinsertion.md))
- arq async queue native to asyncio over Celery's bolt-on async
  ([ADR-0005](../../docs/decisions/0005-arq-vs-celery.md))

Custom paths require an ADR justifying why the native path didn't work.

### IV. Prompt-Injection Surface = OWASP Top-1

The app takes user-supplied documents and feeds them to a tool-using LLM
with access to a glossary store, file storage, and a job queue. The
threat model is `/security-review`-mandatory for any PR that:

- Adds new user input pathways into prompts (upload, paste, URL).
- Touches auth, secrets, file paths, or shell execution.
- Includes user-supplied data in any LLM call.

PRs touching these surfaces without a security-review note in the PR
description must be rejected by reviewers.

### V. Bounded Context, No Speculative Docs

Sessions and PRs must protect the context window: bounded file reads,
no whole-repo dumps, no "just-in-case" documentation. Document what you
*touched* and what *bit you* — not tutorial-style overviews.

- Use `Read` with `offset+limit` for files > 200 lines.
- Prefer targeted `Grep` over reading whole files to find one symbol.
- No "how this works" docs unless a concrete reader needs them.
- Three similar lines beats a premature abstraction.

## Technology Stack Requirements

Authoritative source: [`CLAUDE.md`](../../CLAUDE.md) *Technology Stack* section.

Locked-in choices (each backed by an ADR in `docs/decisions/`):

| Layer | Choice | ADR |
|---|---|---|
| Translation model | `qwen-mt-turbo` (DashScope intl) | [0001](../../docs/decisions/0001-qwen-mt-turbo.md) |
| LLM SDK | `openai` Python SDK + compatible endpoint | [0002](../../docs/decisions/0002-openai-sdk-vs-dashscope-sdk.md) |
| PDF processing | PyMuPDF 1.26.x — direct reinsertion | [0003](../../docs/decisions/0003-pymupdf-direct-reinsertion.md) |
| OCR | PaddleOCR 3.x (PP-OCRv5) | [0004](../../docs/decisions/0004-paddleocr-pp-ocrv5.md) |
| Job queue | arq 0.27 + Redis 7 | [0005](../../docs/decisions/0005-arq-vs-celery.md) |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async | [0006](../../docs/decisions/0006-postgresql-vs-sqlite.md) |
| DOCX | python-docx 1.2.0, run-level replacement | [0007](../../docs/decisions/0007-run-level-text-replacement.md) |
| LLM batching | Sentinel-joined batches, ~10 cells/call | [0008](../../docs/decisions/0008-sentinel-batched-translate.md) |
| Review UI | shadcn Table + Textarea, NOT Monaco DiffEditor | [0009](../../docs/decisions/0009-cat-tool-segment-table.md) |
| PDF fonts | Bundled Noto CJK + Noto Sans (VN/Latin) | [0010](../../docs/decisions/0010-bundled-noto-fonts.md) |

Changing any of these requires a superseding ADR.

## Development Workflow

The project uses **Spec-Driven Development** via Spec-Kit. Authoritative
flow for any feature larger than a one-line fix:

```
/speckit.constitution   (rarely — only when amending this file)
/speckit.specify        — what to build (one feature, one spec)
/speckit.clarify        — de-risk ambiguous areas (recommended)
/speckit.plan           — technical implementation plan
/speckit.tasks          — actionable task breakdown
/speckit.taskstoissues  — push tasks to GitHub Issues
/speckit.analyze        — cross-artifact consistency check
/speckit.implement      — execute
```

`/speckit.checklist` may be inserted after `/speckit.plan` for quality gates.

Devs not using Claude Code can use Cursor, Copilot, Codex, Gemini, or
any of the 30+ agents Spec-Kit supports — the slash commands are
installed per-agent via `specify init . --here --integration <agent>`.

**Pull-request gates** (encoded in `.github/PULL_REQUEST_TEMPLATE.md`):

- [ ] Linked Issue / Spec
- [ ] Eval delta documented (if any model-touching code changed)
- [ ] Security-review note (if Principle IV applies)
- [ ] Tests added/updated for deterministic code
- [ ] No layout regression on hero paths (if PDF/DOCX/PPTX pipeline touched)
- [ ] CLAUDE.md / constitution / ADR updated if a locked-in choice changed

## Governance

This constitution supersedes all other practices. Amendments require:

1. A PR modifying `.specify/memory/constitution.md` with the change.
2. A new or updated ADR in `docs/decisions/` documenting the reasoning.
3. Maintainer approval.
4. Migration plan if existing code violates the new rule.

Day-to-day questions about *how to do something* belong in `CLAUDE.md`
and `docs/`; this file is for *what we will not compromise on*.

**Version**: 1.0.0 | **Ratified**: 2026-05-22 | **Last Amended**: 2026-05-22
