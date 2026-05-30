"""Regenerate the License Management backlog (tasks.json, PROGRESS.md, featurelist.json,
FEATURELIST.md) from one data source.

Tasks are the License_Management_WBS.xlsx tasks, ported Java/Spring -> Python:
  Flyway->Alembic, AWS Secrets Manager->pydantic-settings SecretStr,
  OncePerRequestFilter->FastAPI middleware, @Scheduled->arq cron,
  Redisson->redis-py SETNX lock, JUnit/Testcontainers->pytest, k6->locust.
State owned by verify_task.py.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (task_id, name, layer, priority, days, deps, [(suffix, behavior, verification), ...])
PHASES = [
    ("PHASE 1 — DB Schema & Key Gen", [
        ("TASK-1.1", "Design Database Schema for License Tables", "DB", "Critical", 2, [], [
            ("a", "Alembic `upgrade head` creates licenses + license_activities cleanly and is idempotent (re-run is a no-op).",
             "cd backend && uv run alembic upgrade head && uv run alembic upgrade head"),
            ("b", "licenses.key_hash has a UNIQUE constraint; tier and status are DB enums.",
             "cd backend && uv run pytest -o addopts=\"\" tests/db/test_license_schema.py -k unique_keyhash_and_enums -q"),
            ("c", "Composite index on (status, expired_at) exists for cron efficiency.",
             "cd backend && uv run pytest -o addopts=\"\" tests/db/test_license_schema.py -k composite_index -q"),
            ("d", "Foreign keys enforced: licenses.customer_id and license_activities.license_id.",
             "cd backend && uv run pytest -o addopts=\"\" tests/db/test_license_schema.py -k foreign_keys -q"),
        ]),
        ("TASK-1.2", "Implement Secure License Key Generation Algorithm", "BE", "Critical", 2, ["TASK-1.1"], [
            ("a", "Raw key never persisted; only sha256(raw_key) is written to licenses.key_hash.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_keygen.py -k only_hash_persisted -q"),
            ("b", "Generated key matches the XXXX-XXXX-XXXX-XXXX format.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_keygen.py -k format_pattern -q"),
            ("c", "Signing secret is read from settings SecretStr (env), never hard-coded.",
             "cd backend && ! grep -rEi 'signing_secret\\s*[:=]\\s*[\"\\'][^\"\\']' src/app && uv run pytest -o addopts="" tests/test_license_keygen.py -k secret_from_settings -q"),
            ("d", "10k generated keys are unique; generator module has 100% line coverage.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_keygen.py -k uniqueness --cov=app.licensing.keygen --cov-fail-under=100 -q"),
        ]),
    ]),
    ("PHASE 2 — Backend Core Logic", [
        ("TASK-2.1", "API Create License (Admin) with Idempotency", "BE/DB", "Critical", 3, ["TASK-1.1", "TASK-1.2"], [
            ("a", "POST /api/admin/licenses rejects an invalid request body with 422/400 + field errors.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_admin_licenses.py -k invalid_body -q"),
            ("b", "Non-admin caller gets 403; admin gets 201 with the raw key returned exactly once.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_admin_licenses.py -k rbac_and_one_time_key -q"),
            ("c", "Created license persists status=PENDING with a CREATED row in license_activities.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_admin_licenses.py -k persists_pending_and_audit -q"),
            ("d", "Repeating the same Idempotency-Key does not create a duplicate license.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_admin_licenses.py -k idempotent_create -q"),
        ]),
        ("TASK-2.2", "API Activate License with Distributed Lock", "BE", "Critical", 4, ["TASK-2.1"], [
            ("a", "First valid activation returns 200 + ACTIVE and sets activated_at/expired_at.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_activate.py -k first_activation_succeeds -q"),
            ("b", "Concurrent activations of one key yield exactly one 200; the rest get 409.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_activate_concurrency.py -k only_one_wins -q"),
            ("c", "Activating an already-activated key returns 400.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_activate.py -k already_activated_400 -q"),
            ("d", "Redis key license:{key_hash} is written with TTL ~= expired_at - now.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_activate.py -k cache_ttl_matches_expiry -q"),
            ("e", "Redis lock (SETNX lock:activate:{hash} EX 10) is always released, even on exception.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_activate.py -k lock_released_on_exception -q"),
        ]),
        ("TASK-2.3", "License Validation Middleware", "BE", "Critical", 3, ["TASK-2.2"], [
            ("a", "A valid ACTIVE key in X-License-Key on /api/v1/** passes the middleware.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_middleware.py -k active_key_passes -q"),
            ("b", "Missing/invalid/expired key returns 403 {error: LICENSE_INVALID, code: E4030}.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_middleware.py -k invalid_key_403_body -q"),
            ("c", "On cache miss the middleware queries the DB and repopulates Redis with remaining TTL.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_middleware.py -k cache_miss_repopulate -q"),
            ("d", "Middleware does NOT run on /api/admin/** or /activate.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_license_middleware.py -k excludes_admin_and_activate -q"),
        ]),
        ("TASK-2.4", "Background Cron Job — Expiration Reconciliation", "BE", "High", 2, ["TASK-2.2"], [
            ("a", "arq cron (2 AM daily) flips ACTIVE licenses with expired_at < now to EXPIRED.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_expiry_reconciliation.py -k flips_expired_to_expired -q"),
            ("b", "Bulk update is processed in batches of 500 (no single giant transaction).",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_expiry_reconciliation.py -k batches_of_500 -q"),
            ("c", "Redis keys license:{key_hash} for expired licenses are deleted (clock-skew cleanup).",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_expiry_reconciliation.py -k deletes_redis_keys -q"),
            ("d", "Expiry / 7-day-warning events are published for email notification.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_expiry_reconciliation.py -k publishes_expiry_events -q"),
        ]),
    ]),
    ("PHASE 3 — Frontend", [
        ("TASK-3.1", "Admin Dashboard — License Lifecycle Management", "FE", "High", 5, ["TASK-2.1"], [
            ("a", "/admin/licenses table lists licenses with masked key, tier badge, status chip; paginated and sortable.",
             "cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'table lists masked sortable'"),
            ("b", "Create-license modal posts to the API; one-time key dialog shows and copies the raw key.",
             "cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'create one-time key copy'"),
            ("c", "Filters (tier/status/date) are reflected in URL search params and survive reload.",
             "cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'filters persist in url'"),
            ("d", "Bulk Suspend/Revoke works on multi-select; detail drawer shows activity timeline + Extend Expiry.",
             "cd frontend && npx playwright test e2e/admin-licenses.spec.ts -g 'bulk actions and detail drawer'"),
        ]),
        ("TASK-3.2", "Client Activation Screen & Expiry Warning Banner", "FE", "High", 3, ["TASK-2.2"], [
            ("a", "/activate key input auto-formats (XXXX-XXXX) and calls POST /api/licenses/activate.",
             "cd frontend && npx playwright test e2e/activate.spec.ts -g 'autoformat and submit'"),
            ("b", "Success shows tier/expiry/features; INVALID_KEY/ALREADY_ACTIVATED/EXPIRED each render their color + message.",
             "cd frontend && npx playwright test e2e/activate.spec.ts -g 'success and error states'"),
            ("c", "Global expiry banner appears when < 7 days remain; EXPIRED shows a renewal link.",
             "cd frontend && npx playwright test e2e/activate.spec.ts -g 'expiry warning banner'"),
            ("d", "Banner dismiss state persists across reloads via localStorage.",
             "cd frontend && npx playwright test e2e/activate.spec.ts -g 'banner dismiss persists'"),
        ]),
    ]),
    ("PHASE 4 — Testing", [
        ("TASK-4.1", "Concurrency & Time-Travel Testing", "BE", "High", 3, ["TASK-2.2", "TASK-2.3", "TASK-2.4"], [
            ("a", "Double-activation: 20 concurrent workers on one key yield 1x200 / 19x409 deterministically.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api/test_activate_concurrency.py -k twenty_workers_one_winner -q"),
            ("b", "Time-travel (frozen clock): expired_at-1s -> 200, expired_at+1s -> 403.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_time_travel_expiry.py -k boundary_before_after -q"),
            ("c", "Redis TTL precision within +/-2s of DB expired_at; cache-miss repopulates and returns 200.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_redis_ttl.py -k ttl_within_two_seconds -q"),
            ("d", "Cron reconciliation flips injected expired records; full suite green.",
             "cd backend && uv run pytest -o addopts=\"\" tests -k reconciliation -q"),
        ]),
        ("TASK-4.2", "Integration & Security Testing", "BE/DevOps", "Medium", 3, ["TASK-4.1"], [
            ("a", "End-to-end activate flow (activate -> DB -> Redis) green against real PG + Redis testcontainers.",
             "cd backend && uv run pytest -o addopts=\"\" -m integration tests/integration/test_license_e2e.py -q"),
            ("b", "RBAC: a regular user calling admin endpoints receives 403.",
             "cd backend && uv run pytest -o addopts=\"\" tests/api -k rbac_regular_user_forbidden -q"),
            ("c", "Key brute-force/enumeration shown infeasible (sha256 keyspace) and documented.",
             "cd backend && uv run pytest -o addopts=\"\" tests/test_key_bruteforce.py -k enumeration_infeasible -q"),
            ("d", "Load test: 1000 concurrent valid-license requests achieve P99 < 50ms (Redis hit-rate recorded).",
             "cd backend && uv run locust -f load/locustfile.py --headless -u 1000 -r 200 -t 1m --only-summary --csv load/out && uv run python load/check_p99.py load/out_stats.csv 50"),
        ]),
    ]),
]


def short(tid):
    return tid.replace("TASK-", "")


# ---- tasks.json --------------------------------------------------------------
tasks = [{"id": tid, "name": name, "deps": deps, "days": days}
         for _, items in PHASES for tid, name, _, _, days, deps, _ in items]
with open(os.path.join(ROOT, "scripts", "tasks.json"), "w") as f:
    json.dump({"tasks": tasks}, f, indent=2)
    f.write("\n")

# ---- featurelist.json --------------------------------------------------------
features = []
for phase, items in PHASES:
    for tid, name, layer, prio, days, deps, behs in items:
        for suf, behavior, verification in behs:
            features.append({
                "id": f"{short(tid)}-{suf}", "task": tid, "phase": phase,
                "layer": layer, "priority": prio, "behavior": behavior,
                "verification": verification, "state": "TODO", "evidence": None,
            })
doc = {
    "_meta": {
        "schema": "featurelist/v1",
        "project": "License Management System (Python port of License_Management_WBS.xlsx)",
        "stack": "FastAPI + SQLAlchemy 2.0 async + Alembic + PostgreSQL + redis-py + arq; Next.js admin/activation UI; pytest + locust.",
        "owned_by": "scripts/verify_task.py — do NOT hand-edit `state` or `evidence`",
        "fields": {
            "id": "Stable feature id `<task>-<letter>` (e.g. 2.2-e). One observable behavior per entry.",
            "behavior": "The observable behavior this feature must exhibit.",
            "verification": "Runnable command that PROVES the behavior. Exit 0 = pass.",
            "state": "TODO | IN_PROGRESS | BLOCKED | PASSING | FAILED",
            "evidence": "Filled by the verifier on a pass: {date, command, output_excerpt, artifact}. null until proven.",
        },
        "state_enum": ["TODO", "IN_PROGRESS", "BLOCKED", "PASSING", "FAILED"],
        "rules": [
            "One task IN_PROGRESS at a time (RULES.md).",
            "A feature flips to PASSING only when its `verification` command exits 0.",
            "`state`/`evidence` are written by verify_task.py, never by hand.",
            "Rule 9: a task in PROGRESS.md is DONE only when ALL its behaviors are PASSING.",
        ],
    },
    "features": features,
}
with open(os.path.join(ROOT, "featurelist.json"), "w") as f:
    json.dump(doc, f, indent=2, ensure_ascii=False)
    f.write("\n")

# ---- PROGRESS.md -------------------------------------------------------------
rows = []
for _, items in PHASES:
    for tid, name, layer, prio, days, deps, behs in items:
        dep = ", ".join(short(d) for d in deps) or "—"
        rows.append(f"| {short(tid)} | {name} | {layer} | {prio} | {dep} | TODO | | | |")
total = len(tasks)
days_total = sum(t["days"] for t in tasks)
progress = f"""# License Management System — Progress Tracker

Live status for tasks defined in [`FEATURELIST.md`](./FEATURELIST.md) / [`featurelist.json`](./featurelist.json). Governed by [`RULES.md`](./RULES.md).

> ⚠️ **Do NOT hand-edit the Status / Started / Completed cells, roll-up, or changelog.**
> They are written **only** by `scripts/verify_task.py`. Task state is PROJECTED from `featurelist.json` (Rule 9):
> a task is `DONE` only when **all** its behaviors are `PASSING`.

**Status legend:** `TODO` · `IN_PROGRESS` · `BLOCKED` · `DONE`
**Rules:** one task `IN_PROGRESS` at a time · start only when all **Depends on** are `DONE` · verification-gated completion.

## Status board

| Task | Name | Layer | Priority | Depends on | Status | Started | Completed | Notes |
|------|------|-------|----------|-----------|--------|---------|-----------|-------|
""" + "\n".join(rows) + f"""

## Roll-up

| Metric | Value |
|--------|-------|
| Total tasks | {total} |
| DONE | 0 / {total} |
| IN_PROGRESS | 0 |
| BLOCKED | 0 |
| Est. days total | {days_total} |
| Est. days remaining | {days_total} |

## Changelog

<!-- verify_task.py appends one line per state change -->
- _(empty — no tasks started yet)_
"""
with open(os.path.join(ROOT, "PROGRESS.md"), "w") as f:
    f.write(progress)

# ---- FEATURELIST.md ----------------------------------------------------------
md = ["""# License Management System — Feature List (AI-Executable)

> Python port of `License_Management_WBS.xlsx` (tasks unchanged; Java/Spring -> FastAPI/SQLAlchemy/redis/arq).
> Behavior-level source of truth: [`featurelist.json`](./featurelist.json). Live status: [`PROGRESS.md`](./PROGRESS.md). Rules: [`RULES.md`](./RULES.md).

## Stack mapping (Java -> Python)
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
"""]
for phase, items in PHASES:
    md.append(f"\n---\n\n## {phase}\n")
    for tid, name, layer, prio, days, deps, behs in items:
        dep = ", ".join(deps) or "—"
        md.append(f"### {tid} — {name}")
        md.append(f"- **Layer:** {layer} · **Priority:** {prio} · **Est:** {days}d · **Depends on:** {dep}\n")
        md.append("| Feature | Behavior | Verification |")
        md.append("|---------|----------|--------------|")
        for suf, behavior, verification in behs:
            md.append(f"| `{short(tid)}-{suf}` | {behavior} | `{verification}` |")
        md.append("")
n_feat = len(features)
md.append("\n---\n\n## Summary\n")
md.append("| Phase | Tasks | Behaviors | Est. Days |")
md.append("|-------|-------|-----------|-----------|")
for phase, items in PHASES:
    md.append(f"| {phase} | {len(items)} | {sum(len(b[6]) for b in items)} | {sum(b[4] for b in items)} |")
md.append(f"| **TOTAL** | **{total}** | **{n_feat}** | **{days_total}** |")
with open(os.path.join(ROOT, "FEATURELIST.md"), "w") as f:
    f.write("\n".join(md) + "\n")

print(f"Regenerated: {total} tasks, {n_feat} behaviors, {days_total} est-days.")
