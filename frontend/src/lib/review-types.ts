// Review-page types — Segment, SegmentFlag, FlagType, SegmentsResponse
// These types will be consolidated into lib/types.ts by Plan 05.
// Plan 06 defines them here to avoid parallel-execution conflicts.

export type FlagType =
  | "overflow"
  | "glossary_violation"
  | "placeholder_mismatch"
  | "llm_refusal"
  | "smartart"
  | "multi_column_degraded"
  | "figure_passthrough"   // Phase 4: D-04-24 figure/chart pass-through
  | "ocr_page_error";      // Phase 4: D-04-31 OCR failed for this page

export interface SegmentFlag {
  id: string;
  segment_id: string;
  flag_type: FlagType;
  severity: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Segment {
  id: string;
  job_id: string;
  seq_in_job: number;
  source_text: string;
  translated_text: string | null;
  edited_text: string | null;
  expansion_ratio: number | null;
  structural_position?: string | null;
  flags: SegmentFlag[];
  // Phase 4 OCR fields (D-04-26)
  confidence: number | null;
  region_bbox: [number, number, number, number] | null;
  region_label: string | null;
  edited_source_text: string | null;
}

export interface SegmentsResponse {
  segments: Segment[];
  total: number;
}
