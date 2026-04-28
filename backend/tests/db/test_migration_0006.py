"""Wave 0 RED tests: Alembic migration 0006 column additions."""
import pytest


@pytest.mark.unit
def test_migration_0006_adds_confidence_column():
    """Alembic 0006 adds segments.confidence Float nullable column."""
    raise NotImplementedError("RED: implement migration 0006")


@pytest.mark.unit
def test_migration_0006_adds_region_bbox_column():
    """Alembic 0006 adds segments.region_bbox JSON nullable column."""
    raise NotImplementedError("RED: implement migration 0006")
