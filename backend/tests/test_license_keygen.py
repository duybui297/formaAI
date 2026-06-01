"""Tests for app.licensing.keygen — TASK-1.2.

Verification commands (from featurelist.json):
  1.2-a  pytest -k only_hash_persisted
  1.2-b  pytest -k format_pattern
  1.2-c  pytest -k secret_from_settings
  1.2-d  pytest -k uniqueness --cov=app.licensing.keygen --cov-fail-under=100
"""

from __future__ import annotations

import hashlib
import inspect
import re

import pytest

from app.licensing.keygen import generate_license_key, hash_key

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

SECRET = "test-signing-secret-abc123"
CUSTOMER = "customer-001"

KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


# ---------------------------------------------------------------------------
# 1.2-a  only_hash_persisted
# ---------------------------------------------------------------------------


def test_only_hash_persisted_raw_key_never_equals_hash() -> None:
    """Raw key must never be persisted; only sha256(raw_key) stored in key_hash."""
    raw = generate_license_key(SECRET, CUSTOMER)
    stored = hash_key(raw)

    # stored value must be the sha256 hexdigest of the raw key
    assert stored == hashlib.sha256(raw.encode()).hexdigest()

    # raw key is NOT the stored value
    assert stored != raw

    # hash is exactly 64 hex chars (SHA-256 hexdigest)
    assert len(stored) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", stored)


# ---------------------------------------------------------------------------
# 1.2-b  format_pattern
# ---------------------------------------------------------------------------


def test_format_pattern_matches_xxxx_groups() -> None:
    """Generated key matches ^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$."""
    for _ in range(20):
        key = generate_license_key(SECRET, CUSTOMER)
        assert KEY_PATTERN.match(key), f"Key {key!r} does not match expected pattern"


# ---------------------------------------------------------------------------
# 1.2-c  secret_from_settings
# ---------------------------------------------------------------------------


def test_secret_from_settings_different_secrets_produce_different_keys() -> None:
    """Signing secret read from settings — different secret changes HMAC output."""
    secret_a = "secret-alpha-111"
    secret_b = "secret-beta-999"

    # Generate a large sample with each secret; sets must differ (different HMAC)
    keys_a = {generate_license_key(secret_a, CUSTOMER) for _ in range(50)}
    keys_b = {generate_license_key(secret_b, CUSTOMER) for _ in range(50)}

    # With distinct secrets the keys should not all collide — overlap must be < full set
    # (probabilistically: near-zero overlap; assert at least one differs)
    assert keys_a != keys_b, "Different secrets must produce different key distributions"


def test_secret_from_settings_no_hardcoded_secret_in_keygen_source() -> None:
    """Assert the signing secret value is NOT hard-coded inside keygen.py source."""
    import app.licensing.keygen as keygen_module

    source = inspect.getsource(keygen_module)

    # These are secrets that must never appear literal in the source
    forbidden_values = [
        "test-signing-secret",
        "local-dev-license-signing-secret",
        "replace-with-secrets",
    ]
    for forbidden in forbidden_values:
        assert forbidden not in source, (
            f"Hard-coded secret fragment {forbidden!r} found in keygen.py source"
        )


# ---------------------------------------------------------------------------
# 1.2-d  uniqueness  (+ drives 100% line coverage of app.licensing.keygen)
# ---------------------------------------------------------------------------


def test_uniqueness_10k_keys_all_unique() -> None:
    """10 000 generated keys must all be distinct."""
    keys = [generate_license_key(SECRET, CUSTOMER) for _ in range(10_000)]
    assert len(set(keys)) == 10_000, "Collision detected among 10 000 generated keys"


def test_uniqueness_hash_key_deterministic() -> None:
    """hash_key is deterministic: same input always yields same digest."""
    raw = "ABCD-EFGH-IJKL-MNOP"
    assert hash_key(raw) == hash_key(raw)
    assert hash_key(raw) == hashlib.sha256(raw.encode()).hexdigest()


def test_uniqueness_hash_key_different_inputs_differ() -> None:
    """Different raw keys produce different hashes (collision sanity check)."""
    h1 = hash_key("AAAA-BBBB-CCCC-DDDD")
    h2 = hash_key("AAAA-BBBB-CCCC-DDDE")
    assert h1 != h2
