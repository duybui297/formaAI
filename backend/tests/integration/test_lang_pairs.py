"""Integration test: LANG-02 — required language pairs in supported list.

No network required — tests pure in-memory data from SUPPORTED_LANGUAGES.
Marked @pytest.mark.integration for consistency with the integration suite.

B5 fix: SUPPORTED_LANGUAGES is list[dict[str, str]] with "code" key — not list[str].
W10 fix: from app.XXX not from backend.src.app.XXX.
"""
from __future__ import annotations

import pytest

# Required language pairs per AICore target market (LANG-02)
REQUIRED_PAIRS = [
    ("vi", "en"),  # Vietnamese <-> English
    ("en", "vi"),
    ("vi", "ja"),  # Vietnamese <-> Japanese
    ("ja", "vi"),
    ("vi", "zh"),  # Vietnamese <-> Chinese (Simplified)
    ("zh", "vi"),
    ("en", "ja"),  # English <-> Japanese
    ("ja", "en"),
]


@pytest.mark.integration
def test_required_lang_pairs_in_supported_list() -> None:
    """LANG-02: All four required language pairs exist in the supported language list.

    B5 fix: SUPPORTED_LANGUAGES is list[dict] — iterate with lang["code"].
    W10 fix: from app.XXX not from backend.src.app.XXX.
    """
    # W10: correct import path
    from app.api.routes.languages import SUPPORTED_LANGUAGES

    # B5: SUPPORTED_LANGUAGES is list[dict[str, str]] with "code" key
    codes = {lang["code"] for lang in SUPPORTED_LANGUAGES}

    for src, tgt in REQUIRED_PAIRS:
        assert src in codes, (
            f"Source language '{src}' missing from SUPPORTED_LANGUAGES. "
            f"Present codes: {sorted(codes)}"
        )
        assert tgt in codes, (
            f"Target language '{tgt}' missing from SUPPORTED_LANGUAGES. "
            f"Present codes: {sorted(codes)}"
        )


@pytest.mark.integration
def test_auto_detect_in_source_options() -> None:
    """LANG-01: 'auto' is available as a source language option."""
    # W10: correct import path
    from app.api.routes.languages import SUPPORTED_LANGUAGES

    # B5: list[dict] iteration
    codes = [lang["code"] for lang in SUPPORTED_LANGUAGES]
    assert "auto" in codes, (
        "SUPPORTED_LANGUAGES must include 'auto' as a source option for D-16 auto-detection"
    )


@pytest.mark.integration
def test_priority_languages_present() -> None:
    """UI-SPEC: Priority languages (Recommended group) must exist."""
    # W10: correct import path
    from app.api.routes.languages import SUPPORTED_LANGUAGES

    # B5: list[dict] iteration
    codes = {lang["code"] for lang in SUPPORTED_LANGUAGES}
    priority = {"vi", "en", "ja", "zh"}
    missing = priority - codes
    assert not missing, (
        f"Priority languages missing from SUPPORTED_LANGUAGES: {missing}"
    )
