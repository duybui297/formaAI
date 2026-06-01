"""
load/seed_key.py — one-shot setup for TASK-4.2-d load test.

Creates one ACTIVE license via the running app's API (admin create + activate),
prints the raw key to stdout so locustfile.py can capture it, and exits.

Idempotent: on re-runs the key is read back from load/.load_test_key (cached).
Delete load/.load_test_key to force re-creation.

Usage (called automatically by locustfile.py on_start, or standalone):
    cd backend
    uv run python load/seed_key.py

Env vars:
    APP_URL              - Base URL of the running app (default: http://localhost:8000)
    ADMIN_EMAIL          - Admin email (default: admin123@gmail.com)
    ADMIN_PASSWORD       - Admin password (default: Admin@123)
    LOAD_LICENSE_KEY     - Skip seed entirely; use this key directly.
    LOAD_CUSTOMER_UUID   - UUID to use as customer_id (defaults to seeded admin UUID)

Outputs one line to stdout: the raw license key (XXXX-XXXX-XXXX-XXXX).
All other output goes to stderr so the caller can capture stdout cleanly.
"""
from __future__ import annotations

import os
import sys

import httpx

APP_URL = os.environ.get("APP_URL", "http://localhost:8000")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin123@gmail.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
# Default to the seeded admin user UUID (from migration 0010_seed_default_user.py)
# so the FK constraint on licenses.customer_id is satisfied.
CUSTOMER_UUID = os.environ.get("LOAD_CUSTOMER_UUID", "00000000-0000-0000-0000-000000000001")

IDEMPOTENCY_KEY = "load-test-seed-key-v1"

# Where the raw key is cached between runs (gitignored)
_HERE = os.path.dirname(os.path.abspath(__file__))
_KEY_CACHE_FILE = os.path.join(_HERE, ".load_test_key")


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _read_cache() -> str | None:
    """Return cached raw key from file, or None."""
    if os.path.exists(_KEY_CACHE_FILE):
        val = open(_KEY_CACHE_FILE).read().strip()
        if val:
            return val
    return None


def _write_cache(raw_key: str) -> None:
    with open(_KEY_CACHE_FILE, "w") as fh:
        fh.write(raw_key)


def seed() -> str:
    """Return a raw license key that is ACTIVE and Redis-cached. Idempotent."""

    # 0. Explicit env override
    pre_set = os.environ.get("LOAD_LICENSE_KEY", "").strip()
    if pre_set:
        _eprint("[seed_key] Using LOAD_LICENSE_KEY from env.")
        return pre_set

    # 1. Cached from previous run
    cached = _read_cache()
    if cached:
        _eprint(f"[seed_key] Using cached key from {_KEY_CACHE_FILE}: {cached[:8]}...")
        # Re-warm Redis in case it was flushed — activate is idempotent (returns 400 if already active)
        with httpx.Client(base_url=APP_URL, timeout=15.0) as client:
            resp = client.post("/licenses/activate", json={"raw_key": cached})
            if resp.status_code == 400:
                _eprint("[seed_key] Already active (Redis warm expected).")
            elif resp.status_code == 200:
                _eprint("[seed_key] Re-activated (Redis re-warmed).")
            else:
                _eprint(f"[seed_key] WARNING: activate returned {resp.status_code}: {resp.text[:80]}")
        return cached

    with httpx.Client(base_url=APP_URL, timeout=15.0) as client:
        # 2. Login as admin to obtain access token
        _eprint(f"[seed_key] POST {APP_URL}/auth/login ...")
        resp = client.post(
            "/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if resp.status_code != 200:
            _eprint(f"[seed_key] Login failed {resp.status_code}: {resp.text}")
            sys.exit(1)
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Create license (idempotent via Idempotency-Key header)
        _eprint("[seed_key] POST /admin/licenses ...")
        resp = client.post(
            "/admin/licenses",
            json={
                "tier": "PRO",
                "customer_id": CUSTOMER_UUID,
                "max_devices": 9999,
            },
            headers={**headers, "Idempotency-Key": IDEMPOTENCY_KEY},
        )
        if resp.status_code not in (200, 201):
            _eprint(f"[seed_key] Create failed {resp.status_code}: {resp.text}")
            sys.exit(1)
        data = resp.json()
        raw_key = data.get("raw_key")

        if raw_key is None:
            # raw_key is only returned once (first 201).  The idempotent repeat
            # returns 201 but with raw_key=null.  Should not happen since we check
            # the cache first, but handle defensively.
            _eprint(
                "[seed_key] ERROR: raw_key missing from response and no cache file found.\n"
                f"Delete the load-test license (idempotency_key='{IDEMPOTENCY_KEY}') "
                "from the DB and retry."
            )
            sys.exit(1)

        # 4. Activate license (populates Redis cache license:{hash})
        _eprint(f"[seed_key] POST /licenses/activate with raw_key={raw_key[:8]}... ...")
        resp = client.post(
            "/licenses/activate",
            json={"raw_key": raw_key},
        )
        if resp.status_code not in (200, 400):
            _eprint(f"[seed_key] Activate failed {resp.status_code}: {resp.text}")
            sys.exit(1)
        if resp.status_code == 400:
            _eprint("[seed_key] License already activated (idempotent re-run).")

    # 5. Cache for future runs
    _write_cache(raw_key)
    _eprint(f"[seed_key] DONE. Active license key cached: {raw_key[:8]}...")
    return raw_key


if __name__ == "__main__":
    print(seed())  # stdout only — captured by caller
