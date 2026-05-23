# Architectural Decision Records (ADRs)

> Lightweight log of significant technical decisions and *why* we made them.
> Following the [Michael Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

## Why ADRs?

Code shows *what* we did. Commit messages show *when*. ADRs answer
**why** — the constraints, alternatives considered, and trade-offs
accepted. Without them, the next dev (or next-quarter-you) will
re-litigate decisions that were already settled.

ADRs are the modern replacement for `DISCUSSION-LOG.md` that GSD used.
Same idea, less verbose, one file per decision.

## When to write an ADR

Write a new ADR whenever a PR does any of the following:

- Adds, removes, or replaces a major dependency (model, framework, DB driver).
- Changes a locked-in technology choice from the Constitution.
- Sets a project-wide convention (naming, layout, error handling).
- Documents a non-obvious trade-off a future reader would re-litigate.

Don't write ADRs for:

- Routine refactors, bug fixes, or feature work that follows existing patterns.
- Decisions covered by the constitution unchanged.
- Implementation details — those belong in code comments or `CLAUDE.md`.

## How to add a new ADR

1. Copy `0000-template.md` to `NNNN-short-slug.md` where `NNNN` is the
   next free number (zero-padded to 4 digits).
2. Fill in the sections (keep it brief — ADRs are reference material,
   not essays).
3. Set status to **Accepted** on merge. Use **Proposed** if you want
   review before merging.
4. If a new ADR supersedes an old one, update the old one's status to
   **Superseded by ADR-NNNN** and link.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-qwen-mt-turbo.md) | Use `qwen-mt-turbo` over generic Qwen models | Accepted |
| [0002](0002-openai-sdk-vs-dashscope-sdk.md) | `openai` SDK + DashScope compatible endpoint | Accepted |
| [0003](0003-pymupdf-direct-reinsertion.md) | PyMuPDF redact-and-reinsert for native PDF | Accepted |
| [0004](0004-paddleocr-pp-ocrv5.md) | PaddleOCR PP-OCRv5 for scanned PDF OCR | Accepted |
| [0005](0005-arq-vs-celery.md) | arq + Redis for async job queue | Accepted |
| [0006](0006-postgresql-vs-sqlite.md) | PostgreSQL 16 over SQLite for jobs DB | Accepted |
| [0007](0007-run-level-text-replacement.md) | Run-level text replacement in python-docx | Accepted |
| [0008](0008-sentinel-batched-translate.md) | Sentinel-joined batches at translator layer | Accepted |
| [0009](0009-cat-tool-segment-table.md) | shadcn Table review UI (not Monaco DiffEditor) | Accepted |
| [0010](0010-bundled-noto-fonts.md) | Bundle Noto fonts for CJK + VN PDF insertion | Accepted |
