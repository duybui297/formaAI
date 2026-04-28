export type JobStatus = "queued" | "running" | "needs_review" | "failed" | "done"
export type JobStage = "parse" | "ocr" | "translate" | "compose" | "reassemble" | "done" | "failed"

// D-10 payload shape — matches SSE event + GET /jobs/{id} response
export interface JobProgress {
  id?: string
  status: JobStatus
  stage: JobStage | null
  segments_done: number
  segments_total: number
  current_batch: number
  retry_count: number
  last_message: string
  // From GET /jobs/{id} — not in SSE payload but merged into TanStack cache
  glossary_id?: string | null
  detected_lang?: string
  original_filename?: string
  source_lang?: string
  target_lang?: string
  input_format?: string
  created_at?: string
  error?: {
    code: string
    message: string
    failing_segments: Array<{ id: string; source_text: string; batch_id: number }>
  }
  // Phase 4: D-04-x SSE stage progress substructure
  stage_progress?: {
    stage: string
    current: number
    total: number
  }
  // Phase 4: D-04-14 low confidence pages for needs_review banner
  low_confidence_pages?: number[]
}

// B5: Language shape matches SUPPORTED_LANGUAGES in Plan 06a (list[dict])
export interface Language {
  code: string
  name: string
  qwen_code: string
}

export interface UploadResponse {
  job_id: string
  has_tracked_changes: boolean
}

export interface LanguagesResponse {
  languages: Language[]
  auto_detect_option: string
}

export interface JobSummary {
  id: string
  original_filename: string
  source_lang: string
  target_lang: string
  input_format: string
  status: JobStatus
  created_at: string
  // Phase 4: D-04-14 low confidence pages (from job metadata)
  low_confidence_pages?: number[]
}

// --- Phase 2 types ---
export type FlagType =
  | "overflow"
  | "glossary_violation"
  | "placeholder_mismatch"
  | "llm_refusal"
  | "smartart"
  | "multi_column_degraded"
  | "figure_passthrough"   // Phase 4: D-04-24 figure/chart pass-through
  | "ocr_page_error"       // Phase 4: D-04-31 OCR failed for this page
export type FlagSeverity = "info" | "warn" | "block"

export interface SegmentFlag {
  id: string
  segment_id: string
  flag_type: FlagType
  severity: FlagSeverity
  details: Record<string, unknown>
  created_at: string
}

export interface Segment {
  id: string
  job_id: string
  seq_in_job: number
  source_text: string
  translated_text: string | null
  edited_text: string | null
  expansion_ratio: number | null
  structural_position?: string | null
  flags: SegmentFlag[]
  // Phase 4 OCR fields (D-04-26)
  confidence: number | null
  region_bbox: [number, number, number, number] | null
  region_label: string | null
  edited_source_text: string | null
}

export interface SegmentsResponse {
  segments: Segment[]
  flag_counts: Record<string, number>   // IN-01: server-computed flag counts by type
  total: number
}

export interface GlossaryTerm {
  id: string
  glossary_id: string
  source_term: string
  target_term: string
  notes: string | null
  created_at: string
}

export interface Glossary {
  id: string
  name: string
  source_lang: string
  target_lang: string
  term_count: number          // IN-03: returned by list API as len(terms)
  created_at: string
  updated_at: string
  terms?: GlossaryTerm[]      // only populated by GET /glossaries/{id}
}
