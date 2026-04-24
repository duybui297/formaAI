"""
Healthcheck script for AI Translation PoC.

Validates:
  1. DashScope intl endpoint reachable + qwen-mt-turbo responds to VN→EN probe (INFRA-01)
  2. terminology param behaviour — output with vs without a term injected (INFRA-02)
  3. PostgreSQL connectivity (skipped with --skip-db)
  4. Redis connectivity + arq queue writable (skipped with --skip-db)
  5. Noto CJK + Noto Sans fonts present at expected Debian bookworm path (INFRA-05)

Exit code:
  0 — all enabled checks passed
  1 — one or more checks failed

Usage:
  # All checks (requires docker services running):
  python scripts/healthcheck.py

  # DashScope + font checks only (before docker services are up):
  python scripts/healthcheck.py --skip-db
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _dashscope_client():
    """Return a sync OpenAI client pointed at DashScope intl."""
    from openai import OpenAI

    api_key = _env("DASHSCOPE_API_KEY")
    base_url = _env(
        "DASHSCOPE_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY is not set in the environment")
    return OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=30.0)


# ---------------------------------------------------------------------------
# Check 1: DashScope connectivity + qwen-mt-turbo VN→EN probe
# ---------------------------------------------------------------------------

def check_dashscope() -> bool:
    """Probe DashScope intl with a 1-sentence Vietnamese→English translation."""
    from openai import AuthenticationError, APIConnectionError, BadRequestError

    print("\n[CHECK 1] DashScope intl — qwen-mt-turbo VN→EN probe")
    try:
        client = _dashscope_client()
    except ValueError as exc:
        print(f"  [FAIL] {exc}")
        return False

    try:
        resp = client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=[{"role": "user", "content": "Xin chào thế giới"}],
            extra_body={
                "translation_options": {
                    "source_lang": "auto",
                    "target_lang": "English",
                }
            },
            max_tokens=50,
        )
        output = resp.choices[0].message.content or ""
        print(f"  [OK] qwen-mt-turbo responded. Output: {output!r}")
        return True

    except AuthenticationError:
        print("  [FAIL] DashScope: 401 Authentication error.")
        print("         If you used a China-region key (from dashscope.aliyun.com),")
        print("         obtain an INTERNATIONAL key from dashscope-intl.aliyuncs.com instead.")
        print("         China-region keys return HTTP 401 on the international endpoint.")
        return False

    except APIConnectionError as exc:
        base_url = _env(
            "DASHSCOPE_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        print(f"  [FAIL] DashScope: Cannot connect to {base_url}")
        print(f"         Error: {exc}")
        return False

    except BadRequestError as exc:
        print(f"  [FAIL] DashScope: Bad request — {exc}")
        return False

    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] DashScope: Unexpected error — {type(exc).__name__}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Check 2: terminology param behaviour (INFRA-02)
# ---------------------------------------------------------------------------

def check_terminology() -> bool:
    """Translate same sentence with and without terminology injection; document difference."""
    from openai import OpenAIError

    print("\n[CHECK 2] DashScope intl — terminology param behaviour (INFRA-02)")
    try:
        client = _dashscope_client()
    except ValueError as exc:
        print(f"  [FAIL] {exc}")
        return False

    text = "Tài liệu kỹ thuật của AICore được viết bằng tiếng Việt."

    try:
        # Without terminology
        r1 = client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=[{"role": "user", "content": text}],
            extra_body={
                "translation_options": {
                    "source_lang": "Vietnamese",
                    "target_lang": "English",
                }
            },
            max_tokens=100,
        )
        without_term = r1.choices[0].message.content or ""

        # With terminology: tài liệu kỹ thuật → technical documentation
        r2 = client.chat.completions.create(
            model="qwen-mt-turbo",
            messages=[{"role": "user", "content": text}],
            extra_body={
                "translation_options": {
                    "source_lang": "Vietnamese",
                    "target_lang": "English",
                    "terms": [
                        {
                            "source": "tài liệu kỹ thuật",
                            "target": "technical documentation",
                        }
                    ],
                }
            },
            max_tokens=100,
        )
        with_term = r2.choices[0].message.content or ""

        term_respected = "technical documentation" in with_term
        print(f"  Without term: {without_term!r}")
        print(f"  With term:    {with_term!r}")
        print(f"  Term respected: {term_respected}")

        if not term_respected:
            print("  [WARN] terminology param: 'technical documentation' not found in output.")
            print("         This may be acceptable (model paraphrase) but warrants review.")

        print("  [OK] terminology probe completed")
        return True

    except OpenAIError as exc:
        print(f"  [FAIL] DashScope terminology probe: {type(exc).__name__}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Check 3: PostgreSQL connectivity
# ---------------------------------------------------------------------------

def check_postgres() -> bool:
    """Connect to PostgreSQL and run SELECT 1."""
    print("\n[CHECK 3] PostgreSQL connectivity")
    database_url = _env("DATABASE_URL")
    if not database_url:
        print("  [FAIL] DATABASE_URL is not set")
        return False

    # Convert asyncpg DSN to psycopg2-compatible if needed
    # psycopg2 expects postgresql:// not postgresql+asyncpg://
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        import psycopg2  # type: ignore[import-untyped]
        conn = psycopg2.connect(sync_url)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()
        print(f"  [OK] PostgreSQL reachable. SELECT 1 = {result}")
        return True
    except ImportError:
        # psycopg2 not installed in the healthcheck environment — use asyncpg via asyncio
        return _check_postgres_asyncpg(database_url)
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] PostgreSQL: {type(exc).__name__}: {exc}")
        return False


def _check_postgres_asyncpg(database_url: str) -> bool:
    """Fallback: check Postgres via asyncpg (async)."""
    import asyncio

    async def _probe() -> bool:
        try:
            import asyncpg  # type: ignore[import-untyped]
            # asyncpg expects postgresql:// not postgresql+asyncpg://
            dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
            conn = await asyncpg.connect(dsn)
            result = await conn.fetchval("SELECT 1")
            await conn.close()
            print(f"  [OK] PostgreSQL reachable via asyncpg. SELECT 1 = {result}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] PostgreSQL (asyncpg): {type(exc).__name__}: {exc}")
            return False

    return asyncio.run(_probe())


# ---------------------------------------------------------------------------
# Check 4: Redis connectivity + arq queue writable
# ---------------------------------------------------------------------------

def check_redis() -> bool:
    """Ping Redis and verify arq queue is writable."""
    print("\n[CHECK 4] Redis connectivity + arq queue")
    redis_url = _env("REDIS_URL", "redis://redis:6379/0")

    try:
        import redis as redis_lib  # type: ignore[import-untyped]

        client = redis_lib.Redis.from_url(redis_url, socket_connect_timeout=5)
        pong = client.ping()
        if not pong:
            print("  [FAIL] Redis PING returned False")
            return False

        # Verify we can write to a test key (arq uses Redis for job queues)
        client.set("healthcheck:test", "1", ex=10)
        val = client.get("healthcheck:test")
        client.delete("healthcheck:test")
        client.close()

        print(f"  [OK] Redis reachable. PING={pong}, write/read test: {val!r}")
        return True

    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] Redis: {type(exc).__name__}: {exc}")
        print(f"         URL: {redis_url}")
        return False


# ---------------------------------------------------------------------------
# Check 5: Noto fonts present (INFRA-05)
# ---------------------------------------------------------------------------

def check_fonts() -> bool:
    """Verify Noto CJK and Noto Sans fonts are installed at the expected Debian bookworm path."""
    print("\n[CHECK 5] Noto fonts (CJK + Vietnamese/Latin)")

    # Primary path on Debian bookworm after fonts-noto-cjk + fonts-noto install
    noto_dir = Path("/usr/share/fonts/opentype/noto")
    noto_truetype_dir = Path("/usr/share/fonts/truetype/noto")

    # Also check fc-list as a fallback (works cross-distro)
    ok = True
    noto_found = False

    # Directory-based check
    for fonts_dir in [noto_dir, noto_truetype_dir]:
        if fonts_dir.exists():
            font_files = list(fonts_dir.iterdir())
            if font_files:
                print(f"  [OK] Font directory exists: {fonts_dir} ({len(font_files)} files)")
                noto_found = True
                break

    if not noto_found:
        # Fallback: fc-list
        try:
            result = subprocess.run(
                ["fc-list", ":lang=zh"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and "Noto" in result.stdout:
                print(f"  [OK] Noto CJK fonts found via fc-list")
                noto_found = True
            else:
                print("  [WARN] No Noto CJK fonts found via fc-list")
                print("         Expected: fonts-noto-cjk installed in Docker image")
                print("         Run: apt-get install -y fonts-noto-cjk fonts-noto && fc-cache -f")
                ok = False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # fc-list not available (not running inside Docker image)
            print("  [SKIP] fc-list not available — skipping font path check")
            print("         (Running outside Docker; fonts check only valid inside the backend container)")
            # Not a failure outside Docker
            ok = True

    # Check for Noto Sans (Vietnamese/Latin)
    try:
        result = subprocess.run(
            ["fc-list", ":lang=vi"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            vn_fonts = [line for line in result.stdout.splitlines() if "Noto" in line]
            if vn_fonts:
                print(f"  [OK] Noto Vietnamese fonts found: {len(vn_fonts)} font(s)")
            else:
                print("  [WARN] Vietnamese fonts found but no Noto fonts in list")
                print("         Non-Noto fonts may not render Vietnamese diacritics correctly in PDFs")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # Already handled above

    return ok


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def _load_env_file() -> None:
    """Load .env file if present and not already in environment."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI Translation PoC infrastructure healthcheck"
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip PostgreSQL and Redis checks (use before docker services are up)",
    )
    args = parser.parse_args()

    # Load .env if present
    _load_env_file()

    print("=" * 60)
    print("AI Translation PoC — Infrastructure Healthcheck")
    print("=" * 60)

    checks: list[tuple[str, Callable[[], bool]]] = [
        ("DashScope connectivity", check_dashscope),
        ("terminology param", check_terminology),
    ]

    if not args.skip_db:
        checks += [
            ("PostgreSQL", check_postgres),
            ("Redis", check_redis),
        ]
    else:
        print("\n[INFO] --skip-db: skipping PostgreSQL and Redis checks")

    checks.append(("Noto fonts", check_fonts))

    results: list[tuple[str, bool]] = []
    for name, check_fn in checks:
        try:
            passed = check_fn()
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] {name} raised unexpected exception: {type(exc).__name__}: {exc}")
            passed = False
        results.append((name, passed))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "+" if passed else "X"
        print(f"  [{symbol}] {name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All checks passed.")
        return 0
    else:
        print("One or more checks FAILED. See output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
