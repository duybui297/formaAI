// Review-page types — Segment, SegmentFlag, FlagType, SegmentsResponse
// These types will be consolidated into lib/types.ts by Plan 05.
// Plan 06 defines them here to avoid parallel-execution conflicts.

export type FlagType =
  | "overflow"
  | "glossary_violation"
  | "placeholder_mismatch"
  | "llm_refusal";

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
  flags: SegmentFlag[];
}

export interface SegmentsResponse {
  segments: Segment[];
  total: number;
}
