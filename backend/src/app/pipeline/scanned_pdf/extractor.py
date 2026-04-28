"""
Scanned PDF OCR extractor using PP-StructureV3 (D-04-01, OCR-01).

Wraps PaddleOCR's synchronous Python API in asyncio.to_thread
to avoid blocking the arq event loop (RESEARCH.md §integration patterns).
"""
from __future__ import annotations

import asyncio
import os
from statistics import mean

import numpy as np
import pymupdf
import structlog

from app.pipeline.segment import Segment

log = structlog.get_logger()

# block_labels that pass through untranslated (D-04-24)
# These become kind="figure_passthrough" with placeholder source text
_PASSTHROUGH_LABELS: frozenset[str] = frozenset({
    "image", "chart", "figure",
    "formula", "formula_number",
    "algorithm", "seal", "page_number",
})


def _extract_bbox(block_bbox_raw: object) -> tuple[float, float, float, float]:
    """
    Convert PP-StructureV3 block_bbox to axis-aligned (x0, y0, x1, y1)
    pixel-coordinate floats. PaddleOCR returns one of three shapes:

      1. numpy array shape (4, 2) — polygon of 4 corner points
      2. nested list [[x0,y0], [x1,y0], [x1,y1], [x0,y1]]
      3. flat list/array [x0, y0, x1, y1] (axis-aligned rect)
    """
    arr = np.asarray(block_bbox_raw)
    if arr.ndim == 2 and arr.shape[1] == 2:
        # Polygon: take min/max across the 4 corner points
        x0 = float(arr[:, 0].min())
        y0 = float(arr[:, 1].min())
        x1 = float(arr[:, 0].max())
        y1 = float(arr[:, 1].max())
    elif arr.ndim == 1 and arr.size == 4:
        # Flat rect [x0, y0, x1, y1]
        x0, y0, x1, y1 = (float(v) for v in arr.tolist())
    else:
        raise ValueError(
            f"unexpected block_bbox shape {arr.shape} (expected (4,2) or (4,))"
        )
    return x0, y0, x1, y1


def _normalize_bbox(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    page_w_px: float,
    page_h_px: float,
) -> tuple[float, float, float, float]:
    """Normalize pixel bbox to [0,1] range relative to page dimensions.

    T-04-05: Clamp output to [0,1] using max/min guard — out-of-range bbox
    values from corrupted OCR output are silently clamped, not rejected.
    """
    return (
        max(0.0, min(1.0, x0 / page_w_px)),
        max(0.0, min(1.0, y0 / page_h_px)),
        max(0.0, min(1.0, x1 / page_w_px)),
        max(0.0, min(1.0, y1 / page_h_px)),
    )


async def extract_scanned_pdf_segments(
    doc: pymupdf.Document,
    job_id: str,
    pages_dir: str,
    pipeline: object,
    dpi: int = 300,
    concurrency: int = 1,
) -> tuple[list[Segment], list[int]]:
    """
    OCR stage: extract page images, run PP-StructureV3, build Segment list.

    Returns (segments, low_confidence_pages).
    Page PNGs saved to pages_dir/page-{N}.png (D-04-10).
    PaddleOCR sync API wrapped in asyncio.to_thread (RESEARCH.md §integration patterns).

    Args
    ----
    doc         : pymupdf.Document (already opened by worker)
    job_id      : str — bound to structured log context
    pages_dir   : str — directory for page PNG files
    pipeline    : PP-StructureV3 instance (or mock in tests)
    dpi         : int — page render resolution; default 300 (D-04-10)
    concurrency : int — OCR_PAGE_CONCURRENCY env default 1 (D-04-06)
    """
    os.makedirs(pages_dir, exist_ok=True)
    segments: list[Segment] = []
    low_confidence_pages: list[int] = []
    seq = 0

    for page_num, page in enumerate(doc):
        page_log = log.bind(job_id=job_id, page=page_num)

        # Step 1: Extract page PNG (D-04-10)
        # T-04-04: Release pixmap after save to free ~8MB per page.
        png_path = os.path.join(pages_dir, f"page-{page_num}.png")
        try:
            pixmap = page.get_pixmap(dpi=dpi)
            pixmap.save(png_path)
            del pixmap  # T-04-04: release immediately after save
        except Exception as exc:
            page_log.warning("page_png_extraction_failed", error=str(exc))
            # Emit OCR-error placeholder; continue job (D-04-31)
            segments.append(Segment.from_text(
                source_text="[OCR failed for this page]",
                structural_position=f"page.{page_num}.region.0",
                seq_in_job=seq,
                kind="ocr_text",
                confidence=0.0,
                region_bbox=None,
                region_label=None,
            ))
            seq += 1
            low_confidence_pages.append(page_num)
            continue

        # Step 2: D-04-18 mixed-PDF check — delegate native pages to native path
        native_text = page.get_text().strip()
        if native_text:
            # Page has extractable text: use a simple text segment (native-PDF path)
            segments.append(Segment.from_text(
                source_text=native_text,
                structural_position=f"page.{page_num}.native.0",
                seq_in_job=seq,
                kind="text",
            ))
            seq += 1
            page_log.debug("mixed_pdf_native_page_fallback", chars=len(native_text))
            continue

        # Step 3: Run PP-StructureV3 via asyncio.to_thread (D-04-04)
        try:
            def _sync_predict_with_conf() -> tuple[list[dict], float]:
                output = pipeline.predict(input=png_path)
                if not output:
                    return [], 1.0
                res = output[0]
                json_data = res.json
                # PP-StructureV3 wraps everything under top-level "res" key in
                # paddleocr 3.x; older test fixtures used "layout_parsing_result".
                # Look up each field independently so both shapes work.
                res_data = json_data.get("res") or json_data
                parsing_res = (
                    res_data.get("parsing_res_list")
                    or json_data.get("layout_parsing_result", {}).get("parsing_res_list", [])
                )
                overall_ocr = (
                    res_data.get("overall_ocr_res")
                    or json_data.get("overall_ocr_res", {})
                )
                rec_scores = overall_ocr.get("rec_scores", [])
                page_mean_conf = mean(rec_scores) if rec_scores else 1.0
                return parsing_res, page_mean_conf

            parsing_res, page_mean_conf = await asyncio.to_thread(_sync_predict_with_conf)

        except Exception as exc:
            # Per-page OCR error isolation (D-04-31)
            page_log.warning("ocr_page_failed", error=str(exc))
            segments.append(Segment.from_text(
                source_text="[OCR failed for this page]",
                structural_position=f"page.{page_num}.region.0",
                seq_in_job=seq,
                kind="ocr_text",
                confidence=0.0,
                region_bbox=None,
                region_label=None,
            ))
            seq += 1
            low_confidence_pages.append(page_num)
            continue

        # Step 4: Confidence gate (D-04-02)
        if page_mean_conf < 0.7:
            low_confidence_pages.append(page_num)
            page_log.info("low_confidence_page", confidence=round(page_mean_conf, 3))

        # Step 5: Page pixel dimensions for bbox normalization
        page_w_px = page.rect.width * (dpi / 72.0)
        page_h_px = page.rect.height * (dpi / 72.0)

        # Step 6: Build Segments from parsing_res (sorted by block_order, D-04-20)
        sorted_blocks = sorted(
            parsing_res,
            key=lambda b: (
                b.get("block_order")
                if b.get("block_order") is not None
                else 9999
            ),
        )

        for block in sorted_blocks:
            block_label = block.get("block_label", "text")
            block_content = block.get("block_content", "").strip()
            block_bbox_raw = block.get("block_bbox")
            block_id = block.get("block_id", seq)

            pos = f"page.{page_num}.region.{block_id}"

            # Passthrough labels (D-04-24): figures, charts, formulas
            if block_label in _PASSTHROUGH_LABELS:
                segments.append(Segment.from_text(
                    source_text="[Figure on left]",
                    structural_position=pos,
                    seq_in_job=seq,
                    kind="figure_passthrough",
                    confidence=page_mean_conf,
                    region_bbox=None,  # no bbox needed for placeholder
                    region_label=block_label,
                ))
                seq += 1
                continue

            if not block_content:
                continue

            # Compute normalized bbox
            region_bbox = None
            if block_bbox_raw is not None:
                try:
                    x0, y0, x1, y1 = _extract_bbox(block_bbox_raw)
                    region_bbox = _normalize_bbox(x0, y0, x1, y1, page_w_px, page_h_px)
                except Exception as exc:
                    page_log.warning(
                        "bbox_extraction_failed",
                        block_id=block_id,
                        error=str(exc),
                    )

            segments.append(Segment.from_text(
                source_text=block_content,
                structural_position=pos,
                seq_in_job=seq,
                kind="ocr_text",
                confidence=page_mean_conf,
                region_bbox=region_bbox,
                region_label=block_label,
            ))
            seq += 1

        page_log.info(
            "ocr_page_complete",
            confidence=round(page_mean_conf, 3),
            block_count=len(sorted_blocks),
        )

    return segments, low_confidence_pages
