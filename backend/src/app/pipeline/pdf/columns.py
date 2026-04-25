"""
PDF column clustering heuristic.

PDF-04 + D-03-03: Cluster text blocks by x-coordinate midpoint into columns.
Uses histogram gap detection — no ML dependencies, pure stdlib.

Returns (column_groups, is_degraded):
  - 0 detected gaps: 1 column (flat, not degraded)
  - 1 detected gap: 2 columns (left + right, sorted top-to-bottom each)
  - 2+ detected gaps: 3+ columns → degraded → flat reading order + is_degraded=True

D-03-03 threshold: gap must span >= 30% of page width (gap_threshold=0.30).
[ASSUMED: A5 — 20 bins adequate for A4/Letter; adjust gap_min_bins if false positives occur]
"""
from __future__ import annotations


def _find_gaps(histogram: list[int], min_width_bins: int) -> list[int]:
    """
    Return list of midpoint bin indices where zero-density runs exist BETWEEN
    two occupied regions. Leading and trailing zero-runs are NOT counted as gaps
    (they represent page margins, not column separators).

    A gap must have min_width_bins consecutive zero-count bins and be flanked by
    at least one non-zero bin on each side.
    """
    gaps: list[int] = []
    run_start: int | None = None
    seen_content = False  # track whether any occupied bins appeared before this zero-run
    for i, count in enumerate(histogram):
        if count == 0:
            if run_start is None and seen_content:
                # Start of a potential gap (only if we have seen content before)
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= min_width_bins:
                # Gap between two occupied regions (not trailing)
                gaps.append((run_start + i) // 2)  # midpoint of gap
            run_start = None
            seen_content = True
    # Trailing zero-run: NOT a column gap (just right-margin whitespace)
    return gaps


def _count_peaks(histogram: list[int]) -> int:
    """
    Count maximal runs of consecutive non-zero bins (column "peaks").
    Used to detect 3+ column layouts where gutters are narrower than gap_threshold
    but the layout still has multiple distinct x-midpoint clusters.
    """
    peaks = 0
    in_peak = False
    for count in histogram:
        if count > 0:
            if not in_peak:
                peaks += 1
                in_peak = True
        else:
            in_peak = False
    return peaks


def cluster_columns(
    text_blocks: list[dict],
    page_width: float,
    gap_threshold: float = 0.30,
    bin_count: int = 20,
) -> tuple[list[list[dict]], bool]:
    """
    Cluster text blocks into columns by x-coordinate midpoint histogram.

    # L2: Single canonical implementation — referenced by 03-VALIDATION.md PDF-04 tests.
    # Do NOT create alternative implementations; run 2-col/3-col tests to validate any changes.

    Parameters
    ----------
    text_blocks : list of pymupdf "dict" text block dicts (type==0 only)
    page_width  : page width in points (page.rect.width)
    gap_threshold : minimum gap width as fraction of page_width (D-03-03: 0.30)
    bin_count   : histogram bins (default 20 — adequate for A4/Letter)

    Returns
    -------
    column_groups : list of block lists, one per column (left-to-right)
    is_degraded   : True if 3+ columns or ambiguous (D-03-03)
    """
    if not text_blocks:
        return [[]], False

    # Compute x-midpoints for each block
    midpoints = [(b["bbox"][0] + b["bbox"][2]) / 2.0 for b in text_blocks]

    # Build histogram of x-midpoints
    bin_width = max(page_width / bin_count, 1.0)  # prevent division by zero
    histogram = [0] * bin_count
    for mid in midpoints:
        bin_idx = min(int(mid / bin_width), bin_count - 1)
        histogram[bin_idx] += 1

    # Minimum gap width in bins: D-03-03 threshold (30% of page)
    gap_min_width = page_width * gap_threshold
    gap_min_bins = max(int(gap_min_width / bin_width), 1)

    gaps = _find_gaps(histogram, gap_min_bins)
    peaks = _count_peaks(histogram)

    # 3+ distinct x-midpoint clusters → degraded regardless of gap width.
    # Captures 3-column layouts whose gutters are narrower than gap_threshold
    # but whose midpoint distribution still shows three peaks.
    if peaks >= 3:
        flat = sorted(text_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
        return [flat], True

    if len(gaps) == 0:
        # Single column: sort top-to-bottom
        flat = sorted(text_blocks, key=lambda b: b["bbox"][1])
        return [flat], False

    elif len(gaps) == 1:
        # Two columns: split at gap midpoint (in page coordinates)
        # gaps[0] is the bin index of the gap midpoint
        split_x = (gaps[0] + 0.5) * bin_width
        left = [b for b in text_blocks if (b["bbox"][0] + b["bbox"][2]) / 2.0 < split_x]
        right = [b for b in text_blocks if (b["bbox"][0] + b["bbox"][2]) / 2.0 >= split_x]
        # Sort each column top-to-bottom
        left.sort(key=lambda b: b["bbox"][1])
        right.sort(key=lambda b: b["bbox"][1])
        return [left, right], False

    else:
        # 2+ wide gaps detected — D-03-03: degrade to flat reading order
        flat = sorted(text_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
        return [flat], True
