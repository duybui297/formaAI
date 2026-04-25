"""
PDF column clustering TDD tests.

Tests PDF-04: cluster_columns heuristic produces correct column groups.
RED until plan 04 implements pipeline/pdf/columns.py.
"""
from __future__ import annotations

import pytest


def _make_block(x0: float, y0: float, x1: float, y1: float) -> dict:
    """Build a minimal pymupdf text block dict with bbox."""
    return {"type": 0, "bbox": (x0, y0, x1, y1), "lines": []}


def test_cluster_columns_empty_returns_single_group():
    """Edge case: no blocks → single empty group, not degraded."""
    from app.pipeline.pdf.columns import cluster_columns
    groups, is_degraded = cluster_columns([], page_width=595.0)
    assert len(groups) == 1
    assert is_degraded is False


def test_cluster_columns_single_col_returns_one_group():
    """PDF-04: single-column layout → 1 group, not degraded."""
    from app.pipeline.pdf.columns import cluster_columns
    # 3 blocks all in the center of page (x midpoint ~297)
    blocks = [
        _make_block(72, 50, 523, 62),
        _make_block(72, 70, 523, 82),
        _make_block(72, 90, 450, 102),
    ]
    groups, is_degraded = cluster_columns(blocks, page_width=595.0)
    assert len(groups) == 1
    assert is_degraded is False
    assert len(groups[0]) == 3


def test_cluster_columns_two_col_returns_two_groups():
    """PDF-04: 2-column layout with gap ≥ 30% page width → 2 groups, not degraded."""
    from app.pipeline.pdf.columns import cluster_columns
    page_width = 595.0
    # Left column: x midpoints around 150 (left half)
    # Right column: x midpoints around 445 (right half)
    # Gap: 300-300 = clear separation
    blocks_left = [
        _make_block(72, 50, 240, 62),     # midpoint: 156
        _make_block(72, 70, 240, 82),     # midpoint: 156
    ]
    blocks_right = [
        _make_block(310, 50, 523, 62),    # midpoint: 416
        _make_block(310, 70, 523, 82),    # midpoint: 416
    ]
    groups, is_degraded = cluster_columns(
        blocks_left + blocks_right, page_width=page_width
    )
    assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"
    assert is_degraded is False


def test_cluster_columns_three_col_returns_degraded():
    """PDF-04 + D-03-03: 3-column layout → is_degraded=True, flat single group."""
    from app.pipeline.pdf.columns import cluster_columns
    page_width = 595.0
    # 3 columns: left ~100, center ~297, right ~490
    blocks = [
        _make_block(60,  50, 180, 62),    # midpoint: 120 (left col)
        _make_block(60,  70, 180, 82),
        _make_block(207, 50, 387, 62),    # midpoint: 297 (center col)
        _make_block(207, 70, 387, 82),
        _make_block(410, 50, 535, 62),    # midpoint: 472 (right col)
        _make_block(410, 70, 535, 82),
    ]
    groups, is_degraded = cluster_columns(blocks, page_width=page_width)
    assert is_degraded is True, "3-column layout should set is_degraded=True"
    assert len(groups) == 1, "Degraded layout should return single flat group"


def test_cluster_columns_two_col_reading_order():
    """PDF-04: blocks in left column appear before right column in output."""
    from app.pipeline.pdf.columns import cluster_columns
    page_width = 595.0
    # Left column block at y=200 (below right block at y=50)
    blocks = [
        _make_block(72,  200, 240, 212),   # left col, lower on page
        _make_block(72,  50,  240, 62),    # left col, higher on page
        _make_block(310, 50,  523, 62),    # right col
    ]
    groups, is_degraded = cluster_columns(blocks, page_width=page_width)
    if not is_degraded and len(groups) == 2:
        # Each column sorted top-to-bottom
        left_col = groups[0]
        assert left_col[0]["bbox"][1] < left_col[-1]["bbox"][1], "Left col should be top-to-bottom"
