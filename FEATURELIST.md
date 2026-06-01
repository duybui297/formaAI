# License Management System — Feature List (AI-Executable)

> Python port of `License_Management_WBS.xlsx` (tasks unchanged; Java/Spring → FastAPI/SQLAlchemy/redis/arq).
> Behavior-level source of truth: [`featurelist.json`](./featurelist.json). Live status: [`PROGRESS.md`](./PROGRESS.md). Rules: [`RULES.md`](./RULES.md).

## Stack mapping (Java → Python)
| WBS (Java) | This project (Python) |
|------------|------------------------|
| Flyway | Alembic |
| AWS Secrets Manager | pydantic-settings `SecretStr` (env) |
| Spring Security `OncePerRequestFilter` | FastAPI middleware + dependency |
| Redisson lock | redis-py `SETNX lock:activate:{hash} EX 10` |
| `@Scheduled` | arq cron job |
| JUnit/Mockito/Testcontainers | pytest + pytest-asyncio + testcontainers |
| JMeter / k6 | locust |
| Next.js 14 | Next.js (repo frontend) |

## Agent loop
1. `python3 scripts/verify_task.py next` — next eligible task (deps DONE, none active).
2. `python3 scripts/verify_task.py start TASK-x.y` — claim it.
3. Implement the behaviors below; make each verification command exit 0.
4. `python3 scripts/verify_task.py verify TASK-x.y` — runs every behavior, projects PROGRESS (DONE when all PASSING).
5. Never hand-edit state.

**Agents:** `ai-translation-backend-dev` (BE/Python) · `frontend-feature-builder` (FE) · `playwright-feature-verifier` (e2e).

---

## PHASE 1 — DB Schema & Key Gen

### TASK-1.1 — Design Database Schema for License Tables
- **Layer:** DB · **Priority:** Critical · **Est:** 2d · **Depends on:** —

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `1.1-a` | Alembic `upgrade head` creates licenses + license_activities cleanly and is idempotent (re-run is a no-op). | `cd backend && uv run alembic upgrade head && uv run alembic upgrade head` |
| `1.1-b` | licenses.key_hash has a UNIQUE constraint; tier and status are DB enums. | `cd backend && uv run pytest -o addopts="" tests/db/test_license_schema.py -k unique_keyhash_and_enums -q` |
| `1.1-c` | Composite index on (status, expired_at) exists for cron efficiency. | `cd backend && uv run pytest -o addopts="" tests/db/test_license_schema.py -k composite_index -q` |
| `1.1-d` | Foreign keys enforced: licenses.customer_id and license_activities.license_id. | `cd backend && uv run pytest -o addopts="" tests/db/test_license_schema.py -k foreign_keys -q` |

### TASK-1.2 — Implement Secure License Key Generation Algorithm
- **Layer:** BE · **Priority:** Critical · **Est:** 2d · **Depends on:** TASK-1.1

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `1.2-a` | Raw key never persisted; only sha256(raw_key) is written to licenses.key_hash. | `cd backend && uv run pytest -o addopts="" tests/test_license_keygen.py -k only_hash_persisted -q` |
| `1.2-b` | Generated key matches the XXXX-XXXX-XXXX-XXXX format. | `cd backend && uv run pytest -o addopts="" tests/test_license_keygen.py -k format_pattern -q` |
| `1.2-c` | Signing secret is read from settings SecretStr (env), never hard-coded. | `cd backend && uv run pytest -o addopts="" tests/test_license_keygen.py -k secret_from_settings -q` |
| `1.2-d` | 10k generated keys are unique; generator module has 100% line coverage. | `cd backend && uv run pytest -o addopts="" tests/test_license_keygen.py -k uniqueness --cov=app.licensing.keygen --cov-fail-under=100 -q` |

---

## PHASE 2 — Backend Core Logic

### TASK-2.1 — API Create License (Admin) with Idempotency
- **Layer:** BE/DB · **Priority:** Critical · **Est:** 3d · **Depends on:** TASK-1.1, TASK-1.2

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `2.1-a` | POST /api/admin/licenses rejects an invalid request body with 422/400 + field errors. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_licenses.py -k invalid_body -q` |
| `2.1-b` | Non-admin caller gets 403; admin gets 201 with the raw key returned exactly once. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_licenses.py -k rbac_and_one_time_key -q` |
| `2.1-c` | Created license persists status=PENDING with a CREATED row in license_activities. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_licenses.py -k persists_pending_and_audit -q` |
| `2.1-d` | Repeating the same Idempotency-Key does not create a duplicate license. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_licenses.py -k idempotent_create -q` |
| `2.1-e` | FE create contract: accepts FE tier vocab (starter/professional/enterprise) + `customer_id` as an EMAIL resolved to an existing user (unknown → 400) + optional max_devices/expired_at; returns 201 `{license:{FE License shape, key_masked, customer_id=email}, raw_key}`. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_licenses.py -k create_fe_contract -q` |

### TASK-2.2 — API Activate License with Distributed Lock
- **Layer:** BE · **Priority:** Critical · **Est:** 4d · **Depends on:** TASK-2.1

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `2.2-a` | First valid activation returns 200 + ACTIVE and sets activated_at/expired_at. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate.py -k first_activation_succeeds -q` |
| `2.2-b` | Concurrent activations of one key yield exactly one 200; the rest get 409. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate_concurrency.py -k only_one_wins -q` |
| `2.2-c` | Activating an already-activated key returns 400. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate.py -k already_activated_400 -q` |
| `2.2-d` | Redis key license:{key_hash} is written with TTL ~= expired_at - now. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate.py -k cache_ttl_matches_expiry -q` |
| `2.2-e` | Redis lock (SETNX lock:activate:{hash} EX 10) is always released, even on exception. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate.py -k lock_released_on_exception -q` |

### TASK-2.3 — License Validation Middleware
- **Layer:** BE · **Priority:** Critical · **Est:** 3d · **Depends on:** TASK-2.2

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `2.3-a` | A valid ACTIVE key in X-License-Key on /api/v1/** passes the middleware. | `cd backend && uv run pytest -o addopts="" tests/test_license_middleware.py -k active_key_passes -q` |
| `2.3-b` | Missing/invalid/expired key returns 403 {error: LICENSE_INVALID, code: E4030}. | `cd backend && uv run pytest -o addopts="" tests/test_license_middleware.py -k invalid_key_403_body -q` |
| `2.3-c` | On cache miss the middleware queries the DB and repopulates Redis with remaining TTL. | `cd backend && uv run pytest -o addopts="" tests/test_license_middleware.py -k cache_miss_repopulate -q` |
| `2.3-d` | Middleware does NOT run on /api/admin/** or /activate. | `cd backend && uv run pytest -o addopts="" tests/test_license_middleware.py -k excludes_admin_and_activate -q` |

### TASK-2.4 — Background Cron Job — Expiration Reconciliation
- **Layer:** BE · **Priority:** High · **Est:** 2d · **Depends on:** TASK-2.2

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `2.4-a` | arq cron (2 AM daily) flips ACTIVE licenses with expired_at < now to EXPIRED. | `cd backend && uv run pytest -o addopts="" tests/test_expiry_reconciliation.py -k flips_expired_to_expired -q` |
| `2.4-b` | Bulk update is processed in batches of 500 (no single giant transaction). | `cd backend && uv run pytest -o addopts="" tests/test_expiry_reconciliation.py -k batches_of_500 -q` |
| `2.4-c` | Redis keys license:{key_hash} for expired licenses are deleted (clock-skew cleanup). | `cd backend && uv run pytest -o addopts="" tests/test_expiry_reconciliation.py -k deletes_redis_keys -q` |
| `2.4-d` | Expiry / 7-day-warning events are published for email notification. | `cd backend && uv run pytest -o addopts="" tests/test_expiry_reconciliation.py -k publishes_expiry_events -q` |

### TASK-2.5 — Admin License CRUD APIs
- **Layer:** BE · **Priority:** High · **Est:** 3d · **Depends on:** TASK-2.1, TASK-2.2
- Backend endpoints powering the admin dashboard (TASK-3.1): list/filter/paginate, detail, activities, suspend/revoke, extend.

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `2.5-a` | GET /api/admin/licenses returns the FE-contract envelope `{licenses[], total, page, page_size}` (items use FE `License` shape: `key_masked`, …); filter tier/status/issued_after/issued_before + sort_by/sort_dir; admin-gated (non-admin 403). | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_license_crud.py -k list_filter_paginate -q` |
| `2.5-b` | GET /api/admin/licenses/{id} returns the FE `License` shape (`id`, `key_masked`, `tier`, `status`, `customer_id`, `max_devices`, `issued_at`, `activated_at`, `expired_at`); unknown id → 404; non-admin → 403. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_license_crud.py -k detail_and_404 -q` |
| `2.5-c` | GET /api/admin/licenses/{id}/activities returns a bare `LicenseActivity[]` (`id`, `license_id`, `action`, `actor`, `detail`, `created_at`) newest-first; admin-gated. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_license_crud.py -k activities_timeline -q` |
| `2.5-d` | POST /api/admin/licenses/suspend and /api/admin/licenses/revoke take a bulk `{ids:[...]}` body, transition each (→SUSPENDED / →REVOKED), append an activity row per license, invalidate each Redis key; admin-gated. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_license_crud.py -k suspend_revoke -q` |
| `2.5-e` | POST /api/admin/licenses/{id}/extend takes an absolute `{expired_at:"<ISO>"}` body, sets expired_at, appends an EXTENDED activity row, refreshes Redis TTL, returns the updated `License`. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_license_crud.py -k extend_expiry -q` |
| `2.5-f` | Read endpoints (list/detail/activities) + filters speak FE vocab: tier starter/professional/enterprise (↔TRIAL/PRO/ENTERPRISE), status lowercase incl `pending` (↔BE enum), customer_id as owner email; FE-vocab filter params decoded to BE enum. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_license_crud.py -k fe_vocab_mapping -q` |

---

## PHASE 3 — Frontend

### TASK-3.1 — Admin Dashboard — License Lifecycle Management
- **Layer:** FE · **Priority:** High · **Est:** 5d · **Depends on:** TASK-2.1

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.1-a` | /admin/licenses table lists licenses with masked key, tier badge, status chip; paginated and sortable. | `cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'table lists masked sortable'` |
| `3.1-b` | Create-license modal posts to the API; one-time key dialog shows and copies the raw key. | `cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'create one-time key copy'` |
| `3.1-c` | Filters (tier/status/date) are reflected in URL search params and survive reload. | `cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'filters persist in url'` |
| `3.1-d` | Bulk Suspend/Revoke works on multi-select; detail drawer shows activity timeline + Extend Expiry. | `cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'bulk actions and detail drawer'` |

### TASK-3.2 — Client Activation Screen & Expiry Warning Banner
- **Layer:** FE · **Priority:** High · **Est:** 3d · **Depends on:** TASK-2.2

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.2-a` | /activate key input auto-formats (XXXX-XXXX) and calls POST /api/licenses/activate. | `cd frontend && npx playwright test e2e/activate.spec.ts -g 'autoformat and submit'` |
| `3.2-b` | Success shows tier/expiry/features; INVALID_KEY/ALREADY_ACTIVATED/EXPIRED each render their color + message. | `cd frontend && npx playwright test e2e/activate.spec.ts -g 'success and error states'` |
| `3.2-c` | Global expiry banner appears when < 7 days remain; EXPIRED shows a renewal link. | `cd frontend && npx playwright test e2e/activate.spec.ts -g 'expiry warning banner'` |
| `3.2-d` | Banner dismiss state persists across reloads via localStorage. | `cd frontend && npx playwright test e2e/activate.spec.ts -g 'banner dismiss persists'` |

### TASK-3.3 — Pricing → Self-serve License (user-facing)
- **Layer:** FE/BE · **Priority:** High · **Est:** 3d · **Depends on:** TASK-2.1, TASK-3.2
- **Audience:** `/pricing` = user-facing (pick a plan → get a license); `/admin/licenses` = admin (manage all).

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.3-a` | POST /api/licenses/checkout (authenticated user) creates a PENDING license of the chosen tier for the CURRENT user (customer_id=current_user), returns the raw key once. Not admin-gated. | `cd backend && uv run pytest -o addopts="" tests/api/test_checkout.py -k self_serve_creates_pending -q` |
| `3.3-b` | Plan→tier mapping is correct (Free→TRIAL, Pro→PRO, Business→ENTERPRISE) with per-tier max_devices/validity; invalid plan rejected. | `cd backend && uv run pytest -o addopts="" tests/api/test_checkout.py -k plan_tier_mapping -q` |
| `3.3-c` | /pricing plan CTA opens an email lead-capture popup (no self-serve key dialog, no checkout call); valid email → POST /api/leads → thank-you. | `cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plan opens lead capture'` |
| `3.3-d` | /pricing plan names/features are aligned to the license tiers (TRIAL/PRO/ENTERPRISE). | `cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plans aligned to tiers'` |

### TASK-3.4 — User Registration
- **Layer:** FE/BE · **Priority:** High · **Est:** 2d · **Depends on:** —
- Code exists (BE `POST /auth/register`, FE `/register`) but untested — verify-existing + fill gaps.

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.4-a` | POST /auth/register creates an active, NON-admin user (is_active=true, is_superuser=false), returns 201; password stored hashed (never plaintext). | `cd backend && uv run pytest -o addopts="" tests/api/test_register.py -k creates_active_non_admin -q` |
| `3.4-b` | Registering an already-used email returns 409 Conflict (no duplicate user). | `cd backend && uv run pytest -o addopts="" tests/api/test_register.py -k duplicate_email_conflict -q` |
| `3.4-c` | Weak/short password (<8 chars) or invalid email is rejected with 422. | `cd backend && uv run pytest -o addopts="" tests/api/test_register.py -k invalid_input_rejected -q` |
| `3.4-d` | /register form submits a valid account → user is created and lands authenticated (auto-login → app). | `cd frontend && npx playwright test e2e/register.spec.ts -g 'register success'` |
| `3.4-e` | Client validation: password mismatch / invalid email shows an error and blocks submit. | `cd frontend && npx playwright test e2e/register.spec.ts -g 'register validation'` |

### TASK-3.5 — Pricing Lead Capture + Activate Fix
- **Layer:** FE/BE/DB · **Priority:** High · **Est:** 2d · **Depends on:** TASK-3.2, TASK-3.3
- Normal users no longer self-serve a license from `/pricing`: plan CTAs now capture a marketing-lead email. Also fixes the broken `/activate` request/response contract. The BE `POST /api/licenses/checkout` endpoint is retained (admin/internal) but no longer called by `/pricing`.

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.5-a` | Alembic `upgrade head` creates a `leads` table (id, email, plan, created_at), cleanly + idempotently. | `cd backend && uv run pytest -o addopts="" tests/db/test_leads_schema.py -k leads_table -q` |
| `3.5-b` | POST /api/leads stores `{email, plan}` → 201; invalid email → 422; open (no auth — it's a lead, not a license). | `cd backend && uv run pytest -o addopts="" tests/api/test_leads.py -k creates_lead -q` |
| `3.5-c` | POST /api/licenses/activate accepts `{raw_key}` and returns `{tier, status, expiry, features[]}` (features from the tier plan); bad key → documented error. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate.py -k activate_response_contract -q` |
| `3.5-d` | /activate submits `{raw_key}` (not `{key}`) and renders tier/expiry/features on success (fixes 422 + undefined display). | `cd frontend && npx playwright test e2e/activate.spec.ts -g 'activate success contract'` |

### TASK-3.6 — Admin User Management
- **Layer:** FE/BE/DB · **Priority:** High · **Est:** 3d · **Depends on:** TASK-3.4
- New admin tab `/admin/users`: list/search/paginate, create, activate/deactivate, promote/demote admin, soft-delete. Guards prevent self-harm and removing the last admin.

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.6-a` | Alembic `upgrade head` adds nullable `users.deleted_at` (soft-delete marker), cleanly + idempotently. | `cd backend && uv run pytest -o addopts="" tests/db/test_user_schema.py -k users_deleted_at -q` |
| `3.6-b` | GET /api/admin/users → `{users[], total, page, page_size}`; search email/name + filter role/active; excludes soft-deleted; admin-gated (403 non-admin). | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_users.py -k list_filter_paginate -q` |
| `3.6-c` | POST /api/admin/users creates `{email, full_name?, password, is_superuser?, is_active?}` → 201 (password hashed, never returned); dup email → 409; invalid email / weak pw → 422. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_users.py -k create_user -q` |
| `3.6-d` | PATCH /api/admin/users/{id} updates full_name/is_active/is_superuser; guards: no self deactivate/demote, last admin cannot be demoted/deactivated → 400/409. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_users.py -k update_guards -q` |
| `3.6-e` | DELETE /api/admin/users/{id} soft-deletes (deleted_at + is_active=false, hidden, cannot log in); no self-delete; last admin cannot be deleted → 400/409. | `cd backend && uv run pytest -o addopts="" tests/api/test_admin_users.py -k soft_delete_guards -q` |
| `3.6-f` | Admin sees a 'Users' tab → /admin/users; non-admin can't see it nor reach the route (guard redirects). | `cd frontend && npx playwright test e2e/admin-users.spec.ts -g 'users tab visible admin only'` |
| `3.6-g` | /admin/users lists users (email/name/role badge/active chip) + search + pagination; create-user dialog; row actions activate/deactivate, promote/demote, delete; own-row actions disabled. | `cd frontend && npx playwright test e2e/admin-users.spec.ts -g 'list create and row actions'` |

### TASK-3.7 — Translation Entitlement Enforcement
- **Layer:** FE/BE · **Priority:** High · **Est:** 3d · **Depends on:** TASK-2.2
- Wires the pricing tiers to real enforcement: translation now requires an ACTIVE license and applies per-tier limits. Replaces the dead `/v1/` middleware approach with a per-request entitlement resolver keyed off the logged-in user's active license. Superusers are exempt (treated as ENTERPRISE).
- **Entitlements:** TRIAL = 5MB / 10 docs-mo / no OCR / no glossary · PRO = 50MB / unlimited / OCR / glossary · ENTERPRISE = 100MB / unlimited / OCR / glossary.

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `3.7-a` | plans.py defines per-tier ENTITLEMENTS (max_file_bytes, monthly_quota, ocr_allowed, glossary_allowed) + a resolver (highest active tier; superuser→ENTERPRISE; none→None). | `cd backend && uv run pytest -o addopts="" tests/test_entitlements.py -k tier_entitlements_and_resolver -q` |
| `3.7-b` | GET /api/licenses/me → `{has_active, tier, max_file_bytes, monthly_quota, quota_used, ocr_allowed, glossary_allowed}`; no active license → has_active=false. | `cd backend && uv run pytest -o addopts="" tests/api/test_entitlements_api.py -k licenses_me -q` |
| `3.7-c` | POST /upload requires an active license → 403 `LICENSE_REQUIRED` when absent; superuser exempt. | `cd backend && uv run pytest -o addopts="" tests/api/test_entitlements_api.py -k upload_requires_license -q` |
| `3.7-d` | POST /upload enforces per-tier max file size (5/50/100MB) → 413 over limit. | `cd backend && uv run pytest -o addopts="" tests/api/test_entitlements_api.py -k per_tier_file_size -q` |
| `3.7-e` | POST /upload enforces monthly quota (TRIAL 10/mo, PRO/ENT unlimited) → 403 `QUOTA_EXCEEDED`; resets per calendar month. | `cd backend && uv run pytest -o addopts="" tests/api/test_entitlements_api.py -k monthly_quota -q` |
| `3.7-f` | OCR + glossary gated by tier: TRIAL requesting OCR / attaching glossary_id → 403 `FEATURE_NOT_IN_PLAN`; PRO/ENT allowed. | `cd backend && uv run pytest -o addopts="" tests/api/test_entitlements_api.py -k ocr_glossary_gated -q` |
| `3.7-g` | Unlicensed user blocked from translate UI (prompt → /pricing, /activate); licensed UI reflects tier (size hint, quota, OCR/glossary disabled on TRIAL). | `cd frontend && npx playwright test e2e/entitlements.spec.ts -g 'translate gated by license and tier'` |
| `3.7-h` | Worker gates auto-detected OCR: scanned PDF + TRIAL owner → worker skips OCR and fails the job with FEATURE_NOT_IN_PLAN (feature=ocr); PRO/ENTERPRISE → OCR runs. | `cd backend && uv run pytest -o addopts="" tests/test_worker_ocr_gate.py -k worker_blocks_ocr_for_trial -q` |

---

## PHASE 4 — Testing

### TASK-4.1 — Concurrency & Time-Travel Testing
- **Layer:** BE · **Priority:** High · **Est:** 3d · **Depends on:** TASK-2.2, TASK-2.3, TASK-2.4

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `4.1-a` | Double-activation: 20 concurrent workers on one key yield 1x200 / 19x409 deterministically. | `cd backend && uv run pytest -o addopts="" tests/api/test_activate_concurrency.py -k twenty_workers_one_winner -q` |
| `4.1-b` | Time-travel (frozen clock): expired_at-1s → 200, expired_at+1s → 403. | `cd backend && uv run pytest -o addopts="" tests/test_time_travel_expiry.py -k boundary_before_after -q` |
| `4.1-c` | Redis TTL precision within +/-2s of DB expired_at; cache-miss repopulates and returns 200. | `cd backend && uv run pytest -o addopts="" tests/test_redis_ttl.py -k ttl_within_two_seconds -q` |
| `4.1-d` | Cron reconciliation flips injected expired records; full suite green. | `cd backend && uv run pytest -o addopts="" tests -k reconciliation -q` |

### TASK-4.2 — Integration & Security Testing
- **Layer:** BE/DevOps · **Priority:** Medium · **Est:** 3d · **Depends on:** TASK-4.1

| Feature | Behavior | Verification |
|---------|----------|--------------|
| `4.2-a` | End-to-end activate flow (activate → DB → Redis) green against real PG + Redis testcontainers. | `cd backend && uv run pytest -o addopts="" -m integration tests/integration/test_license_e2e.py -q` |
| `4.2-b` | RBAC: a regular user calling admin endpoints receives 403. | `cd backend && uv run pytest -o addopts="" tests/api -k rbac_regular_user_forbidden -q` |
| `4.2-c` | Key brute-force/enumeration shown infeasible (sha256 keyspace) and documented. | `cd backend && uv run pytest -o addopts="" tests/test_key_bruteforce.py -k enumeration_infeasible -q` |
| `4.2-d` | Load test: 1000 concurrent valid-license requests achieve P99 < 50ms (Redis hit-rate recorded). | `cd backend && uv run locust -f load/locustfile.py --headless -u 1000 -r 200 -t 1m --only-summary --csv load/out && uv run python load/check_p99.py load/out_stats.csv 50` |

---

## Summary

| Phase | Tasks | Behaviors | Est. Days |
|-------|-------|-----------|-----------|
| PHASE 1 — DB Schema & Key Gen | 2 | 8 | 4 |
| PHASE 2 — Backend Core Logic | 4 | 17 | 12 |
| PHASE 3 — Frontend | 4 | 17 | 13 |
| PHASE 4 — Testing | 2 | 8 | 6 |
| **TOTAL** | **12** | **50** | **35** |
