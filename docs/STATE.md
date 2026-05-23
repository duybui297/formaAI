# Project State

> **Last updated:** 2026-05-22
> **Source-of-truth for:** current phase, in-flight work, open issues,
> known blockers. For long-term plan see [`./ROADMAP.md`](./ROADMAP.md);
> for requirements traceability see [`./REQUIREMENTS.md`](./REQUIREMENTS.md).
>
> Migrated from `.planning/HANDOFF.md` (session-handoff format) and
> refreshed for current state. Update this file whenever phase or
> branch state changes meaningfully.

## TL;DR

Phase 1–5 shipped. Phase 06 (generic render-strategy pipeline) spec
merged, planning next. Production deployment work in flight on a separate
worktree. GSD → Spec-Kit workflow migration in progress *this session*.

## Current focus

| Item | Value |
|---|---|
| Active phase | **Phase 06 — render-strategy-pipeline** (SPEC merged via #2213) |
| Branch | `main` |
| Last merged commit | `f7dedde docs(state): record phase 06 context session` |
| Web UI (dev) | `http://localhost:8080` |
| Web UI (prod, in flight) | `https://translate.aicorelabs.click` (pending DNS + cert) |
| Workflow | **Spec-Kit** (just migrated from GSD; see Open Issues) |

## Phase 06 — next actions

1. `/speckit.specify` was effectively done in PR #2213
   (`865aaa9 spec(phase-06): add SPEC.md for render-strategy-pipeline`).
2. Next: `/speckit.clarify` to de-risk ambiguous areas, then
   `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`.
3. SPEC primer lives at
   `.planning/phases/06-render-strategy-pipeline/06-SPEC-BRIEF.md`
   (legacy location — feed it to `/speckit.clarify` as the source brief
   until Phase 06 fully lives under `specs/06-*/`).

## Open issues — surfaced during UAT, NOT yet fixed

| Tag | Symptom | Status | Captured in |
|---|---|---|---|
| D-1 | Figure caption adjacent to image not translated (image_collision pre-check preserves source) | Deferred, source-preserved (graceful) | `.planning/phases/03.3-native-pdf-table-cell-fidelity/03.3-DEFERRED.md` |
| D-2 | Text formatting (color, bold, italic, underline, font family) lost in translated PDF | Deferred | Same DEFERRED.md |
| D-3 | CJK→Latin 5–9× expansion overflows narrow table cells (450 cells in job `e1dcbbf1`) — PyMuPDF draws at scale_low floor, glyphs cramped/clipped | Open — primary driver for Phase 06 | Phase 06 SPEC |
| D-4 | `llm_refusal` false-positive on filenames with `×` (U+00D7) | Cosmetic, deferred | (no-op for output PDF) |
| D-5 | Image-baked speech bubbles on page 5 — invisible to PyMuPDF native extractor | Out of scope (needs OCR fallback for native PDFs) | (separate phase eventually) |
| **D-6** | CORS hardcoded to `localhost:3000` blocking prod calls | **Fixed in this session** (env-driven, see `backend/src/app/api/middleware/cors.py`) | uncommitted |
| **D-7** | Worker container `pull access denied` race in prod compose | **Fixed in this session** (worker has `build:` + `pull_policy: never`) | uncommitted |
| **D-8** | `COPY frontend/public` fails (dir didn't exist) | **Fixed in this session** (`.gitkeep` added) | uncommitted |

## In-flight work (uncommitted on `main`)

```
M  .env.example                                   # CORS_ALLOWED_ORIGINS doc
M  backend/src/app/api/middleware/cors.py         # env-driven origins
M  CLAUDE.md                                      # +5 SPECKIT block from specify init
?? deploy/nginx/ai-translation.conf               # prod nginx site
?? docker-compose.prod.yml                        # prod stack
?? frontend/Dockerfile.frontend.prod              # multi-stage Next.js prod build
?? frontend/public/.gitkeep                       # placeholder so prod COPY works
?? .specify/                                      # Spec-Kit infrastructure
?? .claude/skills/speckit-*                       # 14 spec-kit skills installed
?? docs/                                          # this directory (migration + onboarding)
```

Commit grouping plan (TBD):
1. `feat(infra): production docker-compose + nginx + prod Dockerfile`
2. `fix(api): make CORS allowed origins env-configurable`
3. `chore(workflow): migrate GSD → Spec-Kit; archive .planning/`
4. `docs(onboarding): add docs/ tree (PROJECT, REQUIREMENTS, ROADMAP, STATE, decisions/)`

## Workflow migration (THIS SESSION)

Mid-migration as of 2026-05-22. See
[`./workflow.md`](./workflow.md) for the new flow once written.

| Phase | Status |
|---|---|
| 0 — Install Spec-Kit CLI | ✅ `specify 0.8.13` |
| 1 — Constitution + 10 ADRs | ✅ |
| 2 — Migrate planning docs → `docs/` | ✅ (this file is part of it) |
| 3 — Freeze `.planning/` with archive note | ⏳ next |
| 4 — Write `docs/onboarding/*` | ⏳ |
| 5 — Write `.github/` templates (PR + Issues) | ⏳ |
| 6 — First real Spec-Kit run end-to-end on a Phase 06 task | ⏳ |

## Production deployment (in flight, not yet live)

| Item | Value |
|---|---|
| Server | `letannguyen` (SSH, root access — owner only for now) |
| Target domain | `translate.aicorelabs.click` |
| Compose file | `docker-compose.prod.yml` (host-only ports 7100–7103) |
| nginx site | `deploy/nginx/ai-translation.conf` (HTTP-only; Certbot will add SSL) |
| Existing host services on same box | `aicoresolution-backend-prod:7080`, `aicoresolution-db-prod:5432` |

Outstanding gates before live:
- [ ] DNS A record for `translate.aicorelabs.click` → server IP
- [ ] `alembic upgrade head` after first deploy
- [ ] Certbot cert issued
- [ ] Smoke test through nginx (upload + job poll + download)

## Containers + ops

- `worker` + `api` containers pick up code changes via volume mount on
  `docker compose restart worker api` in **dev** (no rebuild).
- **Prod compose** has no bind mounts — code change → rebuild + restart.
- Web on `http://localhost:8080` in dev (port 3000 was conflicting with a
  Windows process; `docker-compose.yml` remap is permanent).
- `DASHSCOPE_BATCH_SIZE=10` in `.env` (default). Tune up for low-CJK
  source docs; tune down if mismatch logs exceed 10% per job.

## Where to read more

- **What + Why**: [`./PROJECT.md`](./PROJECT.md)
- **Requirement IDs**: [`./REQUIREMENTS.md`](./REQUIREMENTS.md)
- **Phase plan**: [`./ROADMAP.md`](./ROADMAP.md)
- **Locked-in tech choices**: [`./decisions/README.md`](./decisions/README.md)
- **Principles**: [`../.specify/memory/constitution.md`](../.specify/memory/constitution.md)
- **Day-to-day tech detail**: [`../CLAUDE.md`](../CLAUDE.md)
- **Historical artifacts**: `.planning/` (frozen — read-only)
