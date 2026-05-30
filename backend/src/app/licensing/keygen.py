"""Secure license key generation.

Design
------
- Raw key format: XXXX-XXXX-XXXX-XXXX (20 chars incl. hyphens; 16 alphanum)
- Entropy sources: uuid4 (128-bit random) + HMAC-SHA256(secret, timestamp+customer_id)
  Both are mixed via XOR then Base32-encoded to produce the key body.
- Only the SHA-256 hash of the raw key is ever persisted (licenses.key_hash, 64 hex chars).
- The signing secret is read from Settings (SecretStr); never hard-coded here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid


def generate_license_key(signing_secret: str, customer_id: str) -> str:
    """Return a new random license key formatted as XXXX-XXXX-XXXX-XXXX.

    Parameters
    ----------
    signing_secret:
        HMAC signing secret sourced from ``Settings.license_signing_secret``.
        Caller must pass ``settings.license_signing_secret.get_secret_value()``.
    customer_id:
        Opaque customer identifier mixed into the HMAC payload to bind the key
        to a customer context (does not need to be a UUID).
    """
    # 128-bit UUID random bytes — primary entropy source
    uuid_bytes = uuid.uuid4().bytes  # 16 bytes

    # HMAC-SHA256(secret, "<nanosecond_timestamp>:<customer_id>") — secondary entropy
    payload = f"{time.time_ns()}:{customer_id}".encode()
    mac = hmac.new(
        signing_secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).digest()  # 32 bytes

    # XOR first 16 bytes of HMAC with uuid bytes to mix both entropy sources
    mixed = bytes(a ^ b for a, b in zip(uuid_bytes, mac[:16]))

    # Base32-encode → uppercase alphanumeric (A-Z, 2-7); strip padding
    b32 = base64.b32encode(mixed).decode().rstrip("=")

    # Take first 16 chars; group into 4×4 with hyphens → XXXX-XXXX-XXXX-XXXX
    body = b32[:16].upper()
    return f"{body[0:4]}-{body[4:8]}-{body[8:12]}-{body[12:16]}"


def hash_key(raw_key: str) -> str:
    """Return SHA-256 hexdigest of *raw_key* (64 hex chars).

    This is the value stored in ``licenses.key_hash``.  The raw key is never
    persisted — only this hash is.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()
