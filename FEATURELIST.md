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
| `3.3-c` | /pricing (user view) plan CTA calls checkout → shows one-time key dialog + a link to /activate. | `cd frontend && npx playwright test e2e/pricing.spec.ts -g 'plan checkout issues key'` |
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
