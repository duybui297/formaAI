# Session Log — read this FIRST every new session

> **Rule:** At the start of every session, read this file top-to-bottom to recover prior context
> (decisions, infra setup, open gaps). Append a new `## Session N` block at the end when meaningful
> work is done. Do NOT delete past entries. Newest at the bottom.

---

## Project snapshot (current)

- **Repo:** `ai-translation` (Python/FastAPI backend + Next.js frontend). On top of it we are building a **License Management System** — a Python port of `License_Management_WBS.xlsx` (Java/Spring → FastAPI/SQLAlchemy/redis/arq). Tasks unchanged from the WBS; only the stack changed.
- **Verification-driven workflow** (custom, in this repo):
  - `featurelist.json` — behavior-level source of truth: `{id, behavior, verification, state, evidence}`. **Script-owned** — never hand-edit `state`/`evidence`.
  - `PROGRESS.md` — task board; state is **projected** from featurelist.json (Rule 9: task DONE only when ALL its behaviors PASSING).
  - `FEATURELIST.md` — human-readable task list (tasks → behaviors → verification commands).
  - `RULES.md` — the binding rules (single-active task, dependency gate, verification-gated DONE, no hand-editing state, honesty).
  - `scripts/verify_task.py` — the state machine. Commands: `next | start TASK-x | verify <id|TASK-x|all> | reconcile | block TASK-x "reason" | status`. Running `verify` executes each behavior's shell command; exit 0 → PASSING + evidence; then re-projects PROGRESS.
  - `scripts/tasks.json` — task manifest (id, name, deps, days).
  - `scripts/gen_backlog.py` — regenerator (⚠️ STALE: has the original 10 license tasks; TASK-3.3 + TASK-3.4 were added in-place to the live files only. Do NOT run gen_backlog.py — it would reset states. Live files are the truth.)
- **Agents** (`.claude/agents/`): `ai-translation-backend-dev` (BE/Python), `frontend-feature-builder` (FE), `playwright-feature-verifier` (e2e). Loop per task: `start` → delegate to agent(s) → `verify`.

## Backlog status: 11/12 DONE, 1 BLOCKED  (run `python3 scripts/verify_task.py status` for live)

DONE: 1.1 DB schema · 1.2 keygen · 2.1 admin create+idempotency · 2.2 activate+redis lock · 2.3 validation middleware · 2.4 expiry cron (arq) · 3.1 admin dashboard (FE) · 3.2 activation screen (FE) · 3.3 pricing self-serve checkout · 3.4 user registration · 4.1 concurrency/time-travel tests.
BLOCKED: **4.2** Integration & Security — 4.2-a/b/c PASS; **4.2-d** (load P99<50ms @1000u) is infra-blocked (single dev box hits ~250ms; needs separate load-gen host + multi-node deploy). Blocked via verify_task, honest.

## Conventions / gotchas learned (IMPORTANT)
- **Verification commands** use `cd backend && uv run pytest -o addopts="" ...` (bare `pytest`/`alembic` not on PATH; `-o addopts=""` drops the repo's global `--cov-fail-under=80` gate for single-file runs). Frontend: `cd frontend && npx playwright test ...` / `npx vitest run ...`.
- **Backend routers have NO `/api` prefix.** Next.js `next.config.mjs` rewrites `/api/:path*` → backend `/:path*` (STRIPS `/api`). FE `authFetch`/`apiFetch` prepend `/api`. So a backend route must be e.g. `/licenses/checkout`, and the browser calls `/api/licenses/checkout`. (A bug where license routers had `/api` prefix caused 404s in the browser — fixed.)
- **Tests vs real app:** Playwright e2e for FE tasks were written **hermetic with `page.route` mocks** (no live backend). This HID a gap: TASK-3.1 admin dashboard FE is mocked, but the backend only implements `POST /admin/licenses` (create). Missing GET list/detail/activities + suspend/revoke/extend → admin dashboard will 404 in a real browser. (See Open Gaps.)
- Mock-passing ≠ real. When a behavior is verified via a mocked e2e, the backend endpoint may not exist.

## Local run / infra (this machine)
- `RUN.md` has full instructions. Quick: `make up` (docker, build first — NOT bare `docker compose up`, the worker pulls a non-existent image otherwise).
- **Docker postgres host port is 5433** (not 5432) — a local **DBngin Postgres 17** holds 5432 and auto-respawns (can't kill via CLI). docker-compose postgres `ports: "5433:5432"`; api reaches it internally as `postgres:5432`.
- **Root `.env`** (compose `env_file`) needs `SECRET_KEY` + `LICENSE_SIGNING_SECRET` (added) besides `DASHSCOPE_API_KEY` etc. `backend/.env` is for local (non-docker) runs.
- Redis: `redis-server` available via brew for local runs; docker provides its own redis.
- After fresh docker DB: `docker compose exec api alembic upgrade head` (migrations through `0012_license_idempotency_key`).
- Code is **hot-reloaded** in docker: backend `./backend/src` bind-mounted + uvicorn `--reload`; frontend `src`/`public` bind-mounted + `next dev`. No rebuild needed for code changes — only for Dockerfile or new runtime deps.

## Demo accounts
- Admin: `admin123@gmail.com` / `Admin@123` (seeded, `is_superuser=true`).
- User (non-admin): `user@demo.com` / `User@12345` (registered).
- Demo flow: register → login → `/pricing` pick plan (self-serve license, get raw key) → `/activate` enter key. Admin manages at `/admin/licenses`.

## Open gaps / TODO (next sessions)
1. **Admin License CRUD APIs missing** (backend): `admin_licenses.py` only has `POST` create. Need GET list (+filter/paginate), GET `/{id}`, GET `/{id}/activities`, POST `/suspend`, POST `/revoke`, POST `/{id}/extend`. FE already calls these. Proposed as a new task → run through the loop. **Then** switch e2e 3.1 to hit the real backend instead of `page.route` mocks.
2. **4.2-d** load test: needs separate load-gen host + multi-replica deploy to genuinely meet P99<50ms. Re-run `verify 4.2-d` on proper infra to unblock.
3. `scripts/gen_backlog.py` is stale (missing 3.3/3.4) — update it if a full regen is ever needed, or delete to avoid accidental state reset.
4. **Checkpoint committed** on branch `feat/license-management` (commit `6d23638`). `.env`/`.claude/` are gitignored (secrets + personal tooling excluded). Not pushed; not merged to `main`.

## Auth/UI fixes done this session (so they aren't re-done)
- `/auth/me` now returns `is_superuser` (UserResponse + register + /me). FE `AuthUser` has `is_superuser?`.
- `AppSidebar` gates the Admin section on `user?.is_superuser` (fetches `/me` via useQuery).
- `(app)/admin/layout.tsx` route guard: non-admin → redirect `/dashboard` (defense-in-depth; backend still 403s).
- Login page register link was commented out → uncommented (`/login` → "Create one" → `/register`).

---

## Session 1 — 2026-05-29 → 2026-05-30

**What was built:** the whole verification workflow scaffolding (RULES.md, featurelist.json, PROGRESS.md, FEATURELIST.md, scripts/verify_task.py + tasks.json), the architecture docs (BACKEND.md, FRONTEND.md, per-module + aggregate ARCHITECTURE.md), and the License Management feature end-to-end through TASK-1.1 → 4.1 + 3.3 (pricing self-serve) + 3.4 (registration). 11/12 tasks DONE, 4.2 BLOCKED (4.2-d infra).

**Notable fixes:** uv-run verify commands; docker postgres 5433; root .env secrets; pull-denied (`make up`); is_superuser exposure + admin gating + admin route guard; login→register link; **license router `/api`-prefix 404 bug** (browser couldn't reach checkout/admin/activate — routers now have no `/api` prefix to match the proxy that strips it).

**Left open:** admin CRUD backend endpoints (gap hidden by mocked e2e), 4.2-d infra, gen_backlog stale, no commits yet.

---

## Session 2 — 2026-05-30

**What was built (4 new tasks through the verify loop, board now 15/16 DONE; 4.2 still BLOCKED):**

- **TASK-2.5 Admin License CRUD APIs** — the backend the admin dashboard (3.1) was calling but that didn't exist (gap was hidden by mocked e2e). `GET /admin/licenses` (paginate/filter/sort), `GET /{id}`, `GET /{id}/activities`, bulk `POST /suspend` + `/revoke` ({ids}), `POST /{id}/extend` ({expired_at}). Then reconciled BE→FE contract: list envelope key `licenses[]`, `key_masked`, bare activities array, and a **vocab mapping layer** (`app/licensing/vocab.py`) — admin API speaks FE vocab (tier starter/professional/enterprise, lowercase status incl `pending`, `customer_id` as **email** resolved to a user) while the domain keeps TRIAL/PRO/ENTERPRISE + uppercase + UUID. `key_masked` = `****-****-****-XXXX` (last 4 of key_hash — raw key never persisted). Create decoupled into `AdminCreateLicenseRequest` (email/FE-tier) vs `InternalCreateLicenseRequest` (UUID/BE-enum) so self-serve checkout (3.3) didn't break.

- **TASK-3.5 Pricing Lead Capture + Activate Fix** — removed self-serve key issuance from `/pricing`; plan CTAs now open an email lead-capture popup → `POST /api/leads` (new `leads` table, migration 0014) → thank-you. BE `/licenses/checkout` retained but unused by pricing. Also fixed the **broken /activate**: FE sent `{key}` but BE wanted `{raw_key}` (422); BE `ActivateResponse` now returns `{tier, status, expiry, features[]}` (features from `plans.TIER_FEATURES`). Rewrote 3.3-c to the popup behaviour.

- **TASK-3.6 Admin User Management** — new admin sidebar tab `/admin/users`. BE `admin_users.py`: list (search/role/active filter, paginate, excludes soft-deleted), create (409 dup / 422 weak), PATCH (activate/deactivate + promote/demote), DELETE (**soft-delete** via new `users.deleted_at`, migration 0015). Guards: no self deactivate/demote/delete, can't remove the last admin. `get_current_active_user` now rejects deleted/inactive users (login blocked). FE page mirrors licenses; own-row actions disabled.

- **TASK-3.7 Translation Entitlement Enforcement** — the pricing tiers were **marketing-only** (no enforcement; any logged-in user could translate unlimited). Now enforced: `app/licensing/plans.py` ENTITLEMENTS (TRIAL 5MB/10-mo/no-OCR/no-glossary · PRO 50MB/∞/OCR/glossary · ENTERPRISE 100MB/∞/OCR/glossary) + resolver `app/licensing/entitlements.py` (highest active tier; **superuser→ENTERPRISE**; none→None). `/upload` now requires an active license (403 LICENSE_REQUIRED), enforces per-tier file size (413), monthly quota (403 QUOTA_EXCEEDED, counts Job rows in the calendar month — Job.user_id already existed), and OCR/glossary gates (403 FEATURE_NOT_IN_PLAN). Worker also gates **auto-detected** scanned-PDF OCR (3.7-h, `translate_worker.py` `case "scanned_pdf"`): TRIAL owner → job FAILED with FEATURE_NOT_IN_PLAN/ocr; null-owner legacy jobs skip the gate. New `GET /api/licenses/me` returns the entitlement summary; FE `TranslatorWorkspace` blocks unlicensed users (→ /pricing, /activate) and `UploadForm` reflects tier (size hint, quota remaining, OCR/glossary disabled on TRIAL).

**Demo flow change:** normal user `/pricing` → email popup (NO key). Keys are admin-issued at `/admin/licenses` → given to customer → `/activate`. Translation now requires an ACTIVE license (admin/superuser exempt).

**Docs:** added root **README.md** (overview + quick-start + admin API + doc map). Run guide already in RUN.md.

**Migrations to apply on deploy:** `docker compose exec api alembic upgrade head` → 0013 (license EXTENDED enum), 0014 (leads), 0015 (users.deleted_at).

**Left open / caveats:**
- ~69 pre-existing BE failures in unrelated suites (upload/SSE/segments/healthcheck/**jobs**: `test_jobs.py`/`test_jobs_download.py` lack an auth mock); not caused by this session — needs a conftest auth fixture sweep.
- Pre-existing FE TS errors in non-license files (jobs/review, forgot-password, UploadForm.test, useJobProgress).
- 4.2-d load test still BLOCKED (needs separate load-gen host).
- No commits yet this session.

---

## Session 3 — 2026-06-06

**What was changed:** Lead capture now sends an SMTP notification email to a configured inbox after storing the lead row. `backend/src/app/api/routes/leads.py` gained `_send_lead_notification_email(email, plan)` and calls it after `lead_captured`. Added `lead_notification_to` config in `backend/src/app/core/config.py`, plus `LEAD_NOTIFICATION_TO` docs in `.env.example`.

**Behavior:** `POST /leads` still succeeds even when email is not configured or SMTP send fails. In those cases the lead is still stored and the backend logs either `lead_email_not_configured_skipping_notification` or `lead_notification_send_failed`. When configured, the email is sent to the sales/admin inbox with the submitter email set as `Reply-To`.

**Verification:** `ReadLints` clean for edited backend files; `python3 -m compileall backend/src/app/api/routes/leads.py backend/src/app/core/config.py` passed.

**Follow-up enhancement:** Lead notification emails now include an HTML version for better readability and support multiple recipients via comma-separated `LEAD_NOTIFICATION_TO` values.

**Additional enhancement:** Lead emails now show a friendly plan label (`Free`, `Pro`, `Business`) plus capture metadata (`Captured at (UTC)` and `Source page: /pricing`).

**Email template redesign (Session 3 end):** Redesigned both auth email templates with AI Translation context — dark header (`#1a1a2e`), indigo CTA button (`#6366f1`), mobile-safe inline CSS table layout. **ForgotPassword** (`_send_reset_email`): clean HTML template with branded header, CTA button, fallback link, security notice, and a one-liner about Forma preserving document format. **Welcome** (`_send_welcome_email`): new function called after `user_registered` in the `register` endpoint; 2x2 feature grid (DOCX/PDF/PPTX support, 88+ languages, custom glossaries, side-by-side review) + "Start translating" CTA + "Activate license" secondary link. Both include plain-text fallbacks. **E2E verified:** `welcome_email_sent` logged for `test-welcome-june6@example.com` after `POST /auth/register 201`; `reset_email_sent` logged for same address after `POST /auth/forgot-password 200`.

**Plan subscription email templates (Session 3 end, part 2):**
- **Lead confirmation email** (`_send_lead_confirmation_email` in `leads.py`): sent automatically to the visitor after they submit `POST /leads`. Subject: "Forma — we received your {plan} plan inquiry". Content: acknowledgment, feature highlights (DOCX/PDF/PPTX, 88+ languages, glossaries, side-by-side review), CTA "Learn more about Forma", note about 1 business day response time. `send_email` flag default true. **E2E verified:** `lead_confirmation_sent` logged after lead submission.
- **License delivery email** (`_send_license_delivery_email` in `admin_licenses.py`): sent automatically to the customer when admin creates a license via `POST /admin/licenses` with `send_email: true`. Shows raw license key (monospaced), tier badge, max devices, expiry date, and "Activate your license" CTA. Schema updated: `AdminCreateLicenseRequest.send_email` (bool, default true). **E2E verified:** `license_delivery_email_sent` logged after `POST /admin/licenses` returned raw key `2PBL-SC5G-CXEC-J5KK`.
- **Bug fixed:** `AttributeError: 'str' object has no attribute 'value'` in `create_license` — `result.license.tier` is already an FE string (`"professional"`), not a BE enum. Fixed by using `str()` + `.title()` instead of `TIER_BE_TO_FE` lookup.
- **Bug fixed:** `NameError: name 'get_settings' is not defined` in `admin_licenses.py` — `get_settings` imported from `app.api.deps` (FastAPI dependency) was removed but still used in endpoint signature and `_send_license_delivery_email`. Restored import and used inline `from app.core.config import get_settings as core_get_settings` inside the helper function (standalone call outside request context).
