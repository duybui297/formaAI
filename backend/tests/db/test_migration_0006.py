"""Unit tests: Alembic migration 0006 column additions (Phase 4, OCR-01)."""
from __future__ import annotations

import importlib.util
import inspect
import os

import pytest


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def _import_migration():
    """Import the migration module by file path (name starts with digit, cannot use import)."""
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "src",
        "app",
        "db",
        "migrations",
        "versions",
        "0006_phase4_ocr.py",
    )
    spec = importlib.util.spec_from_file_location("migration_0006", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_migration_0006_has_correct_revision():
    """Migration revision ID matches expected value."""
    m = _import_migration()
    assert m.revision == "0006_phase4_ocr"


@pytest.mark.unit
def test_migration_0006_has_correct_down_revision():
    """Migration down_revision points to previous migration (0005_widen_flag_type)."""
    m = _import_migration()
    assert m.down_revision == "0005_widen_flag_type"


@pytest.mark.unit
def test_migration_0006_adds_confidence_column():
    """upgrade() source contains confidence column addition."""
    m = _import_migration()
    source = inspect.getsource(m.upgrade)
    assert "confidence" in source, "upgrade() must add segments.confidence column"


@pytest.mark.unit
def test_migration_0006_adds_region_bbox_column():
    """upgrade() source contains region_bbox column addition."""
    m = _import_migration()
    source = inspect.getsource(m.upgrade)
    assert "region_bbox" in source, "upgrade() must add segments.region_bbox column"


@pytest.mark.unit
def test_migration_0006_adds_region_label_column():
    """upgrade() source contains region_label column addition."""
    m = _import_migration()
    source = inspect.getsource(m.upgrade)
    assert "region_label" in source, "upgrade() must add segments.region_label column"


@pytest.mark.unit
def test_migration_0006_adds_edited_source_text_column():
    """upgrade() source contains edited_source_text column addition."""
    m = _import_migration()
    source = inspect.getsource(m.upgrade)
    assert "edited_source_text" in source, (
        "upgrade() must add segments.edited_source_text column"
    )


@pytest.mark.unit
def test_migration_0006_downgrade_drops_all_four_columns():
    """downgrade() source drops all four Phase 4 columns."""
    m = _import_migration()
    source = inspect.getsource(m.downgrade)
    for col in ("confidence", "region_bbox", "region_label", "edited_source_text"):
        assert col in source, f"downgrade() must drop {col}"


@pytest.mark.unit
def test_migration_0006_uses_sa_float_for_confidence():
    """upgrade() uses sa.Float() for the confidence column."""
    m = _import_migration()
    source = inspect.getsource(m.upgrade)
    assert "Float" in source, "confidence column must use sa.Float()"


@pytest.mark.unit
def test_migration_0006_uses_sa_json_for_region_bbox():
    """upgrade() uses sa.JSON() for the region_bbox column."""
    m = _import_migration()
    source = inspect.getsource(m.upgrade)
    assert "JSON" in source, "region_bbox column must use sa.JSON()"
