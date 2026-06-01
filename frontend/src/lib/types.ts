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

// --- License Management types (TASK-3.1) ---

export type LicenseTier = "starter" | "professional" | "enterprise"
export type LicenseStatus = "pending" | "active" | "suspended" | "revoked" | "expired"

export interface License {
  id: string
  key_masked: string          // e.g. ****-****-****-AB12
  tier: LicenseTier
  status: LicenseStatus
  customer_id: string | null
  max_devices: number
  issued_at: string
  activated_at: string | null
  expired_at: string | null
}

export interface LicenseActivity {
  id: string
  license_id: string
  action: string
  actor: string | null
  detail: string | null
  created_at: string
}

export interface LicensesListParams {
  tier?: LicenseTier
  status?: LicenseStatus
  issued_after?: string
  issued_before?: string
  page?: number
  page_size?: number
  sort_by?: string
  sort_dir?: "asc" | "desc"
}

export interface LicensesListResponse {
  licenses: License[]
  total: number
  page: number
  page_size: number
}

export interface CreateLicenseRequest {
  tier: LicenseTier
  customer_id?: string
  max_devices?: number
  expired_at?: string
}

export interface CreateLicenseResponse {
  license: License
  raw_key: string
}

// --- License Activation types (TASK-3.2) ---

export type ActivateErrorCode = "INVALID_KEY" | "ALREADY_ACTIVATED" | "EXPIRED"

export interface ActivateLicenseRequest {
  raw_key: string
}

export interface ActivateLicenseResponse {
  id?: string
  tier: string                // backend returns lowercase e.g. "pro", "starter"
  status: string              // backend returns lowercase e.g. "active"
  activated_at?: string | null
  expired_at?: string | null
  expiry: string | null       // ISO date string; null if no expiry
  features: string[]
}

export interface ActivateLicenseError {
  code: ActivateErrorCode
  message: string
}

// --- License Checkout types (TASK-3.3) ---

export type CheckoutPlan = "free" | "pro" | "business"

export interface CheckoutLicenseRequest {
  plan: CheckoutPlan
}

export interface CheckoutLicenseResponse {
  raw_key: string
  /** Backend returns TRIAL | PRO | ENTERPRISE (uppercase) — distinct from admin LicenseTier */
  tier: string
  status: string
  id?: string
  issued_at?: string
  expired_at?: string | null
}

// --- Admin User Management types (TASK-3.6) ---

export interface AdminUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
}

export interface AdminUsersListParams {
  page?: number
  page_size?: number
  search?: string
  role?: "admin" | "user"
  active?: boolean
}

export interface AdminUsersListResponse {
  users: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface CreateAdminUserRequest {
  email: string
  full_name?: string
  password: string
  is_superuser?: boolean
  is_active?: boolean
}

export interface UpdateAdminUserRequest {
  full_name?: string
  is_active?: boolean
  is_superuser?: boolean
}

// --- Entitlement types (TASK-3.7) ---

export type EntitlementTier = "TRIAL" | "PRO" | "ENTERPRISE"

export interface Entitlement {
  has_active: boolean
  tier: EntitlementTier | null
  max_file_bytes: number | null
  monthly_quota: number | null
  quota_used: number
  ocr_allowed: boolean | null
  glossary_allowed: boolean | null
}

// --- Lead Capture types (TASK-3.5) ---

export interface LeadRequest {
  email: string
  plan: CheckoutPlan
}

export interface LeadResponse {
  id: string
  email: string
  plan: string
  created_at: string
}
