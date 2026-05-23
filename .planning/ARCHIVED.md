# .planning/ — ARCHIVED

> **Frozen on:** 2026-05-22
> **Status:** Historical artifacts only. Do NOT modify files in this
> directory. New work belongs in `docs/`, `.specify/`, and `specs/`.

## Why this is frozen

This directory was the workspace for the **GSD (Get Stuff Done) workflow**
during Phase 1 through Phase 5 of the PoC. Starting 2026-05-22 the
project moved to **Spec-Kit** (https://github.com/github/spec-kit)
because:

1. GSD's CLI is Claude-Code-specific; team needs multi-agent support
   (Cursor, Copilot, Codex, etc.).
2. Spec-Kit integrates GitHub Issues natively
   (`/speckit.taskstoissues`).
3. The dozens of per-phase `SUMMARY.md` / `PLAN.md` / `DISCUSSION-LOG.md`
   files added bookkeeping overhead disproportionate to PoC scale.

## What moved where

| Old location | New location | Notes |
|---|---|---|
| `.planning/PROJECT.md` | `docs/PROJECT.md` | Verbatim copy + migration banner |
| `.planning/REQUIREMENTS.md` | `docs/REQUIREMENTS.md` | Same — REQ IDs preserved |
| `.planning/ROADMAP.md` | `docs/ROADMAP.md` | Same |
| `.planning/HANDOFF.md` | `docs/STATE.md` | Re-framed from session-handoff to living state |
| `.planning/codebase/ARCHITECTURE.md` | (kept here for now) | Will move to `docs/architecture.md` in onboarding pass |
| Phase decision logs (`*-DISCUSSION-LOG.md`) | `docs/decisions/00NN-*.md` | Extracted as ADRs (Michael Nygard format) |
| Per-phase `SUMMARY.md` files | (stay here, frozen) | Historical execution trail; not actively read |
| Per-phase `SPEC.md` / `PLAN.md` (Phase 1–5) | (stay here, frozen) | Reference only |
| Constitution-equivalent (`CLAUDE.md` rules) | `.specify/memory/constitution.md` | 5 Core Principles |

## What's still authoritative under `.planning/`

Nothing for *new* work. These are the only places code may still
*reference* `.planning/`:

- Phase 06 SPEC primer:
  `.planning/phases/06-render-strategy-pipeline/06-SPEC-BRIEF.md`
  — handed to `/speckit.clarify` as source brief until Phase 06 fully
  lives under `specs/06-*/`.
- Phase 03.3 deferred-items log:
  `.planning/phases/03.3-native-pdf-table-cell-fidelity/03.3-DEFERRED.md`
  — referenced by `docs/STATE.md` open-issues table (D-1, D-2).

When the above two are no longer referenced, they too can be considered
fully frozen.

## New work goes where

| Kind of artifact | Location |
|---|---|
| Project principles | `.specify/memory/constitution.md` |
| Per-feature SPEC + plan + tasks | `specs/NNN-<slug>/` (created by `specify init` / `/speckit.*`) |
| Architectural decisions | `docs/decisions/00NN-<slug>.md` (ADR format) |
| Project-level docs (PROJECT/REQUIREMENTS/ROADMAP/STATE) | `docs/` |
| Onboarding / how-to | `docs/onboarding/` (to be written) |
| Tech stack details | `CLAUDE.md` (top-level) |
| GitHub workflow templates | `.github/` |

## Why we kept the folder instead of deleting

1. Historical trace — phase summaries document HOW the PoC was built;
   useful if Thu or future devs want to retrospect on velocity, scope
   creep, or decision sequence.
2. Zero cost to leave in place — gitignored output, no maintenance burden.
3. Easier to consult old `*-RESEARCH.md` / `*-PATTERNS.md` files than to
   re-derive their insights.

## When to fully delete

Delete `.planning/` when:
- No code references any file in it (grep for `.planning/`).
- No open issue references a `.planning/` document.
- A clean repo audit is in scope (e.g. open-sourcing the project — not
  planned).

Until then: **read-only**.
