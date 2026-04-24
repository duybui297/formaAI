"""Phase 2 config tests (TDD RED -> GREEN).

Tests:
  - Settings.expansion_ratio_thresholds field has correct default JSON
  - Settings.expansion_thresholds_dict returns dict[str, float]
  - Default values: en->vi=1.3, vi->en=0.9, etc.
  - Malformed JSON raises ValidationError (fail-fast startup — T-02-02-01)
  - Non-dict JSON raises ValidationError
  - Non-numeric values raise ValidationError
  - Custom JSON via field value overrides defaults
"""
from __future__ import annotations

import os

import pytest


def make_settings(**kwargs):
    """Helper: create Settings with required env vars + optional overrides."""
    os.environ.setdefault("DASHSCOPE_API_KEY", "sk-test-placeholder")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from app.core.config import Settings

    return Settings(**kwargs)


def test_expansion_thresholds_dict_default_returns_dict() -> None:
    s = make_settings()
    d = s.expansion_thresholds_dict
    assert isinstance(d, dict)


def test_expansion_thresholds_dict_en_vi() -> None:
    s = make_settings()
    assert s.expansion_thresholds_dict["en->vi"] == pytest.approx(1.3)


def test_expansion_thresholds_dict_vi_en() -> None:
    s = make_settings()
    assert s.expansion_thresholds_dict["vi->en"] == pytest.approx(0.9)


def test_expansion_thresholds_dict_ja_vi() -> None:
    s = make_settings()
    assert s.expansion_thresholds_dict["ja->vi"] == pytest.approx(1.5)


def test_expansion_thresholds_dict_vi_ja() -> None:
    s = make_settings()
    assert s.expansion_thresholds_dict["vi->ja"] == pytest.approx(0.9)


def test_expansion_thresholds_dict_vi_zh() -> None:
    s = make_settings()
    assert s.expansion_thresholds_dict["vi->zh"] == pytest.approx(0.85)


def test_expansion_thresholds_dict_en_ja() -> None:
    s = make_settings()
    assert s.expansion_thresholds_dict["en->ja"] == pytest.approx(1.6)


def test_expansion_thresholds_dict_custom_override() -> None:
    """Custom JSON value replaces the default."""
    s = make_settings(expansion_ratio_thresholds='{"en->vi": 2.0, "vi->en": 0.5}')
    d = s.expansion_thresholds_dict
    assert d["en->vi"] == pytest.approx(2.0)
    assert d["vi->en"] == pytest.approx(0.5)
    # Original defaults not present in custom JSON
    assert "ja->vi" not in d


def test_expansion_thresholds_malformed_json_raises_validation_error() -> None:
    """T-02-02-01: Malformed JSON must raise ValidationError at construction time."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="EXPANSION_RATIO_THRESHOLDS"):
        make_settings(expansion_ratio_thresholds="not json at all")


def test_expansion_thresholds_non_dict_json_raises_validation_error() -> None:
    """T-02-02-01: Valid JSON that is not a dict must raise ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_settings(expansion_ratio_thresholds='["en->vi", 1.3]')


def test_expansion_thresholds_non_numeric_value_raises_validation_error() -> None:
    """T-02-02-01: String values in the dict must raise ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_settings(expansion_ratio_thresholds='{"en->vi": "high"}')
