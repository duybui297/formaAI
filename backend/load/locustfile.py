"""
TASK-4.2-d: Load test for the license validation middleware READ path (Redis cache hit).

Measures P99 latency for GET /v1/ping with a VALID, ACTIVE, Redis-cached
X-License-Key header — the O(1) hot path through LicenseValidationMiddleware.

SLA: P99 < 50ms at 1000 concurrent users.

Setup (runs ONCE before spawning users):
    A seed step calls load/seed_key.py to create + activate one license and warm
    the Redis cache (license:{hash}).  All 1000 simulated users share that single
    key so every request is a Redis HIT — no DB fallback.

Task weights:
    - validate_license (90%): GET /v1/ping  with X-License-Key = <active key>
      → exercises ONLY the Redis GET + middleware allow path
    - health_check     (10%): GET /health        (baseline, no middleware overhead)

Usage:
    # From backend/ directory (server must already be running on :8000):
    uv run locust -f load/locustfile.py --headless -u 1000 -r 200 -t 1m \\
        --only-summary --csv load/out

Environment variables:
    LOCUST_HOST        - Base URL (default: http://localhost:8000)
    LOAD_LICENSE_KEY   - Pre-activated raw license key.  If set, seed step is skipped.
    ADMIN_EMAIL        - Admin email for seed step (default: admin123@gmail.com)
    ADMIN_PASSWORD     - Admin password for seed step (default: Admin@123)
"""
from __future__ import annotations

import os
import subprocess
import sys

from locust import HttpUser, between, events, task

# ---------------------------------------------------------------------------
# Global active key — populated once in the test_start event hook
# ---------------------------------------------------------------------------
_ACTIVE_KEY: str | None = None


@events.test_start.add_listener
def on_test_start(environment, **kwargs) -> None:  # type: ignore[override]
    """Seed one active license and warm the Redis cache before load begins."""
    global _ACTIVE_KEY

    # Allow caller to bypass seed step by providing the key directly
    pre_set = os.environ.get("LOAD_LICENSE_KEY", "").strip()
    if pre_set:
        print(f"[locust] Using pre-set LOAD_LICENSE_KEY: {pre_set[:8]}...", file=sys.stderr)
        _ACTIVE_KEY = pre_set
        return

    # Determine path to seed_key.py relative to this file
    here = os.path.dirname(os.path.abspath(__file__))
    seed_script = os.path.join(here, "seed_key.py")

    # Run seed_key.py via uv run python so it picks up the venv
    backend_dir = os.path.dirname(here)
    try:
        result = subprocess.run(
            ["uv", "run", "python", seed_script],
            capture_output=True,
            text=True,
            cwd=backend_dir,
            timeout=30,
        )
    except FileNotFoundError:
        print(
            "[locust] ERROR: 'uv' not found on PATH. Install uv or set LOAD_LICENSE_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("[locust] ERROR: seed_key.py timed out.", file=sys.stderr)
        sys.exit(1)

    # stderr is informational (seed_key prints status there)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    raw_key = result.stdout.strip()
    if result.returncode != 0 or not raw_key:
        print(
            f"[locust] ERROR: seed_key.py failed (exit {result.returncode}). "
            "Cannot proceed without an active license key.",
            file=sys.stderr,
        )
        sys.exit(1)

    _ACTIVE_KEY = raw_key
    print(f"[locust] Active license key seeded: {raw_key[:8]}...", file=sys.stderr)


class LicenseValidationUser(HttpUser):
    """
    Simulates clients hitting the licensed API with a valid, Redis-cached key.

    90% of traffic → GET /v1/ping (license middleware O(1) Redis cache hit)
    10% of traffic → GET /health       (baseline: no middleware overhead)

    Wait time: 0–50ms between tasks (aggressive burst to saturate 1000 users).
    """

    wait_time = between(0, 0.05)
    host = os.environ.get("LOCUST_HOST", "http://localhost:8000")

    @task(9)
    def validate_license(self) -> None:
        """GET /v1/ping — main SLA path.

        Every request carries X-License-Key for a Redis-cached ACTIVE license.
        Middleware performs: Redis GET license:{hash} → HIT → allow → 200.
        No DB access on the hot path.
        """
        key = _ACTIVE_KEY or ""
        with self.client.get(
            "/v1/ping",
            headers={"X-License-Key": key},
            catch_response=True,
            name="GET /v1/ping [license-cached]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 403:
                resp.failure(
                    f"403 LICENSE_INVALID — Redis cache miss or key expired? "
                    f"body={resp.text[:80]}"
                )
            else:
                resp.failure(f"Unexpected {resp.status_code}: {resp.text[:80]}")

    @task(1)
    def health_check(self) -> None:
        """GET /health — baseline latency (no license middleware)."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="GET /health [baseline]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check failed: {resp.status_code}")
