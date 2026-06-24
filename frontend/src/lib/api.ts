import type {
  Language,
  JobProgress,
  JobSummary,
  PaginatedJobsResponse,
  TranslationRow,
  PaginatedTranslationsResponse,
  License,
  Glossary,
  LicenseActivity,
  LicensesListParams,
  LicensesListResponse,
  MyLicensesResponse,
  CreateLicenseRequest,
  CreateLicenseResponse,
  ActivateLicenseRequest,
  ActivateLicenseResponse,
  ActivateLicenseError,
  CheckoutPlan,
  CheckoutLicenseResponse,
  LeadRequest,
  LeadResponse,
  AdminUser,
  AdminUsersListParams,
  AdminUsersListResponse,
  CreateAdminUserRequest,
  UpdateAdminUserRequest,
  Entitlement,
} from "@/lib/types"
import { authFetch } from "@/lib/auth"

// next.config.mjs rewrites /api/* → backend; NEXT_PUBLIC_API_URL overrides for direct calls
const API_BASE = "/api"

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const res = await authFetch(path, init)
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res
}

// B5: returns Language[] matching SUPPORTED_LANGUAGES shape (code/name/qwen_code)
export async function getLanguages(): Promise<Language[]> {
  const res = await apiFetch("/v1/languages")
  const data = await res.json()
  return data.languages as Language[]
}

export async function getGlossaries(): Promise<Glossary[]> {
  const res = await apiFetch("/v1/glossaries")
  const data = await res.json()
  return data.glossaries as Glossary[]
}

export async function getJob(jobId: string): Promise<JobProgress> {
  const res = await apiFetch(`/v1/jobs/${jobId}`)
  return res.json()
}

export async function listJobs(params?: {
  page?: number
  page_size?: number
  sort?: "newest" | "oldest"
}): Promise<PaginatedJobsResponse> {
  const qs = new URLSearchParams()
  if (params?.page != null) qs.set("page", String(params.page))
  if (params?.page_size != null) qs.set("page_size", String(params.page_size))
  if (params?.sort) qs.set("sort", params.sort)
  const query = qs.toString()
  const res = await apiFetch(`/v1/jobs${query ? `?${query}` : ""}`)
  const data = await res.json()
  return data as PaginatedJobsResponse
}

// US-4.1 [BE] — spec-aligned list endpoint
// GET /api/v1/translations?page=&size=&sort= (default sort: -created_at)
// Org-scoped query; response: rows + total + page metadata
export async function listTranslations(params?: {
  page?: number
  size?: 5 | 10 | 25
  sort?: "created_at" | "-created_at"
}): Promise<PaginatedTranslationsResponse> {
  const qs = new URLSearchParams()
  if (params?.page != null) qs.set("page", String(params.page))
  if (params?.size != null) qs.set("size", String(params.size))
  if (params?.sort) qs.set("sort", params.sort)
  const query = qs.toString()
  const res = await apiFetch(`/v1/translations${query ? `?${query}` : ""}`)
  return res.json() as Promise<PaginatedTranslationsResponse>
}

export async function deleteTranslation(jobId: string): Promise<void> {
  // DELETE goes through apiFetch → authFetch → JWT injected automatically.
  // NOTE: previous implementation used bare fetch() which sent no Authorization
  // header, causing the license middleware to short-circuit with 401.
  const res = await apiFetch(`/v1/jobs/${jobId}`, { method: "DELETE" })
  // 204 No Content on success; apiFetch already throws if !res.ok
  await res.text().catch(() => "")
}

export interface CreateJobOptions {
  file: File
  source_lang: string
  target_lang: string
  trackedChangesAction?: "strip" | "preserve"
  glossaryId?: string
  isScannedOverride?: boolean
}

export async function createJob(options: CreateJobOptions): Promise<{ job_id: string; has_tracked_changes: boolean; is_scanned: boolean }> {
  const form = new FormData()
  form.append("file", options.file)
  form.append("source_lang", options.source_lang)
  form.append("target_lang", options.target_lang)
  if (options.trackedChangesAction) {
    form.append("tracked_changes_action", options.trackedChangesAction)
  }
  if (options.glossaryId) {
    form.append("glossary_id", options.glossaryId)
  }
  if (options.isScannedOverride !== undefined) {
    form.append("is_scanned_override", String(options.isScannedOverride))
  }

  const res = await authFetch("/v1/translations", {
    method: "POST",
    body: form,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`Translation submission failed ${res.status}: ${text}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// License Management API (TASK-3.1)
// ---------------------------------------------------------------------------

export async function listLicenses(params: LicensesListParams = {}): Promise<LicensesListResponse> {
  const qs = new URLSearchParams()
  if (params.tier) qs.set("tier", params.tier)
  if (params.status) qs.set("status", params.status)
  if (params.issued_after) qs.set("issued_after", params.issued_after)
  if (params.issued_before) qs.set("issued_before", params.issued_before)
  if (params.page != null) qs.set("page", String(params.page))
  if (params.page_size != null) qs.set("page_size", String(params.page_size))
  if (params.sort_by) qs.set("sort_by", params.sort_by)
  if (params.sort_dir) qs.set("sort_dir", params.sort_dir)
  const query = qs.toString()
  const res = await apiFetch(`/v1/admin/licenses${query ? `?${query}` : ""}`)
  return res.json()
}

export async function createLicense(body: CreateLicenseRequest): Promise<CreateLicenseResponse> {
  const res = await apiFetch("/v1/admin/licenses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function getLicense(id: string): Promise<License> {
  const res = await apiFetch(`/v1/admin/licenses/${id}`)
  return res.json()
}

export async function getLicenseActivities(id: string): Promise<LicenseActivity[]> {
  const res = await apiFetch(`/v1/admin/licenses/${id}/activities`)
  return res.json()
}

export async function suspendLicenses(ids: string[]): Promise<void> {
  await apiFetch("/v1/admin/licenses/suspend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  })
}

export async function revokeLicenses(ids: string[]): Promise<void> {
  await apiFetch("/v1/admin/licenses/revoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  })
}

export async function extendExpiry(id: string, expired_at: string): Promise<License> {
  const res = await apiFetch(`/v1/admin/licenses/${id}/extend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expired_at }),
  })
  return res.json()
}

// ---------------------------------------------------------------------------
// License Activation API (TASK-3.2)
// ---------------------------------------------------------------------------

export interface ActivateResult {
  ok: true
  data: ActivateLicenseResponse
}

export interface ActivateFailure {
  ok: false
  error: ActivateLicenseError
}

/**
 * Activates a license key. Returns a discriminated union so callers can
 * inspect error codes without try/catch.
 */
export async function activateLicense(
  key: string
): Promise<ActivateResult | ActivateFailure> {
  const body: ActivateLicenseRequest = { raw_key: key }
  // throwOnError:false — we read error body ourselves to extract the code
  const res = await authFetch("/v1/licenses/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    throwOnError: false,
  })
  if (res.ok) {
    const data: ActivateLicenseResponse = await res.json()
    return { ok: true, data }
  }
  const json = await res.json().catch(() => ({
    code: "INVALID_KEY" as const,
    message: "Activation failed",
  }))
  return {
    ok: false,
    error: {
      code: json.code ?? "INVALID_KEY",
      message: json.message ?? json.detail ?? "Activation failed",
    },
  }
}

// ---------------------------------------------------------------------------
// License Checkout API (TASK-3.3)
// ---------------------------------------------------------------------------

/**
 * Issues a new license for the authenticated user based on selected plan.
 * Plan→tier: free→TRIAL, pro→PRO, business→ENTERPRISE.
 * Returns raw_key once — caller must show it immediately.
 */
export async function checkoutLicense(
  plan: CheckoutPlan
): Promise<CheckoutLicenseResponse> {
  const res = await authFetch("/v1/licenses/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`Checkout failed ${res.status}: ${text}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Admin User Management API (TASK-3.6)
// ---------------------------------------------------------------------------

export async function listUsers(params: AdminUsersListParams = {}): Promise<AdminUsersListResponse> {
  const qs = new URLSearchParams()
  if (params.page != null) qs.set("page", String(params.page))
  if (params.page_size != null) qs.set("page_size", String(params.page_size))
  if (params.search) qs.set("search", params.search)
  if (params.role) qs.set("role", params.role)
  if (params.active != null) qs.set("active", String(params.active))
  const query = qs.toString()
  const res = await apiFetch(`/v1/admin/users${query ? `?${query}` : ""}`)
  return res.json()
}

export async function createUser(body: CreateAdminUserRequest): Promise<AdminUser> {
  const res = await authFetch("/v1/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    const err = new Error(detail) as Error & { status: number }
    err.status = res.status
    throw err
  }
  return res.json()
}

export async function updateUser(id: string, patch: UpdateAdminUserRequest): Promise<AdminUser> {
  const res = await authFetch(`/v1/admin/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    const err = new Error(detail) as Error & { status: number }
    err.status = res.status
    throw err
  }
  return res.json()
}

export async function deleteUser(id: string): Promise<void> {
  const res = await authFetch(`/v1/admin/users/${id}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    const err = new Error(detail) as Error & { status: number }
    err.status = res.status
    throw err
  }
}

// ---------------------------------------------------------------------------
// Entitlement API (TASK-3.7)
// ---------------------------------------------------------------------------

/**
 * GET /licenses/me — returns the current user's entitlement.
 * Always 200; has_active=false means no active license.
 */
export async function getMyEntitlements(): Promise<Entitlement> {
  const res = await authFetch("/v1/licenses/me", { throwOnError: false })
  if (!res.ok) {
    // Treat any error as unlicensed — graceful degradation
    return {
      has_active: false,
      tier: null,
      max_file_bytes: null,
      monthly_quota: null,
      quota_used: 0,
      ocr_allowed: null,
      glossary_allowed: null,
    }
  }
  return res.json()
}

/**
 * GET /licenses/my-licenses — returns all licenses owned by the authenticated user.
 * Includes PENDING (not yet activated) and ACTIVE/EXPIRED/SUSPENDED/REVOKED licenses.
 * Never returns raw_key — it is only shown once at creation time.
 */
export async function getMyLicenses(): Promise<MyLicensesResponse> {
  const res = await authFetch("/v1/licenses/my-licenses")
  return res.json()
}

// ---------------------------------------------------------------------------
// Lead Capture API (TASK-3.5)
// ---------------------------------------------------------------------------

/**
 * Submits a lead (email + plan) to the backend.
 * Open endpoint — no auth required.
 * Returns 201 { id, email, plan, created_at } on success; throws on 422.
 */
export async function submitLead(
  email: string,
  plan: CheckoutPlan
): Promise<LeadResponse> {
  const body: LeadRequest = { email, plan }
  const res = await fetch(`${API_BASE}/leads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export interface UpdateMeRequest {
  full_name?: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

// ---------------------------------------------------------------------------
// Notifications API
// ---------------------------------------------------------------------------

export async function getNotifications(): Promise<import("@/lib/types").NotificationsResponse> {
  const res = await apiFetch("/v1/notifications")
  return res.json()
}

/**
 * PATCH /auth/me — update the current user's full_name.
 */
export async function updateMe(body: UpdateMeRequest): Promise<import("@/lib/types").AdminUser> {
  const res = await authFetch("/v1/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * POST /auth/me/avatar — upload a new avatar image (multipart/form-data).
 */
export async function uploadAvatar(file: File): Promise<{ avatar_url: string }> {
  const form = new FormData()
  form.append("file", file)
  const res = await authFetch("/v1/auth/me/avatar", {
    method: "POST",
    body: form,
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Upload failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

/**
 * PATCH /auth/me/password — change the current user's password.
 */
export async function changePassword(body: ChangePasswordRequest): Promise<void> {
  const res = await authFetch("/v1/auth/me/password", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
}

// ---------------------------------------------------------------------------
// Notification Preferences API
// ---------------------------------------------------------------------------

export interface NotificationPreferences {
  email_job_complete: boolean
  email_job_failed: boolean
  email_license_expiry: boolean
  email_license_revoked: boolean
  email_marketing: boolean
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
  const res = await authFetch("/v1/auth/me/notifications")
  return res.json()
}

export async function updateNotificationPreferences(
  patch: Partial<NotificationPreferences>
): Promise<NotificationPreferences> {
  const res = await authFetch("/v1/auth/me/notifications", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Translation Defaults API
// ---------------------------------------------------------------------------

export interface TranslationDefaults {
  preferred_source_lang: string | null
  preferred_target_lang: string | null
  default_glossary_id: string | null
  auto_detect: boolean
}

export async function getTranslationDefaults(): Promise<TranslationDefaults> {
  const res = await authFetch("/v1/auth/me/translation-defaults")
  return res.json()
}

export async function updateTranslationDefaults(
  patch: Partial<TranslationDefaults>
): Promise<TranslationDefaults> {
  const res = await authFetch("/v1/auth/me/translation-defaults", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// API Keys
// ---------------------------------------------------------------------------

export interface ApiKeyInfo {
  id: string
  name: string
  key_prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export interface ApiKeyCreated {
  id: string
  name: string
  key_prefix: string
  created_at: string
  raw_key: string
}

export async function listApiKeys(): Promise<ApiKeyInfo[]> {
  const res = await authFetch("/v1/auth/me/api-keys")
  return res.json()
}

export async function createApiKey(name: string): Promise<ApiKeyCreated> {
  const res = await authFetch("/v1/auth/me/api-keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export async function revokeApiKey(keyId: string): Promise<void> {
  const res = await authFetch(`/v1/auth/me/api-keys/${keyId}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok && res.status !== 204) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
}

// ---------------------------------------------------------------------------
// Team Workspace
// ---------------------------------------------------------------------------

export interface WorkspaceMember {
  id: string
  email: string
  full_name: string | null
  role: "owner" | "member"
  joined_at: string
}

export interface WorkspaceInvite {
  id: string
  email: string
  role: string
  status: string
  created_at: string
  expires_at: string
}

export interface WorkspaceInfo {
  members: WorkspaceMember[]
  pending_invites: WorkspaceInvite[]
}

export async function getWorkspace(): Promise<WorkspaceInfo> {
  const res = await authFetch("/v1/auth/me/workspace")
  return res.json()
}

export async function inviteMember(email: string, role: string): Promise<WorkspaceInvite> {
  const res = await authFetch("/v1/auth/me/workspace/invite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, role }),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
  return res.json()
}

export async function revokeInvite(inviteId: string): Promise<void> {
  const res = await authFetch(`/v1/auth/me/workspace/invite/${inviteId}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok && res.status !== 204) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
}

export async function removeMember(memberId: string): Promise<void> {
  const res = await authFetch(`/v1/auth/me/workspace/member/${memberId}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok && res.status !== 204) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
}

// ---------------------------------------------------------------------------
// Webhooks (US-9.4)
// ---------------------------------------------------------------------------

export interface WebhookEndpoint {
  id: string
  name: string
  url: string
  events: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WebhookEndpointCreated {
  id: string
  name: string
  url: string
  events: string[]
  is_active: boolean
  created_at: string
  updated_at: string
  secret: string  // shown only once at creation
}

export interface CreateWebhookPayload {
  name: string
  url: string
  events: string[]
}

export interface UpdateWebhookPayload {
  name?: string
  url?: string
  events?: string[]
  is_active?: boolean
}

export interface WebhookDelivery {
  id: string
  job_id: string
  event_type: string
  attempt: number
  status: "pending" | "success" | "failed"
  request_method: string
  request_url: string
  request_headers: Record<string, string> | null
  response_status_code: number | null
  response_body: string | null
  error_message: string | null
  duration_ms: number | null
  created_at: string
}

export interface WebhookDeliveryList {
  deliveries: WebhookDelivery[]
  total: number
  page: number
  page_size: number
}

export async function listWebhooks(): Promise<WebhookEndpoint[]> {
  const res = await authFetch("/v1/auth/me/webhooks")
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
  return res.json()
}

export async function createWebhook(payload: CreateWebhookPayload): Promise<WebhookEndpointCreated> {
  const res = await authFetch("/v1/auth/me/webhooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
  return res.json()
}

export async function getWebhook(webhookId: string): Promise<WebhookEndpoint> {
  const res = await authFetch(`/v1/auth/me/webhooks/${webhookId}`)
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
  return res.json()
}

export async function updateWebhook(webhookId: string, payload: UpdateWebhookPayload): Promise<WebhookEndpoint> {
  const res = await authFetch(`/v1/auth/me/webhooks/${webhookId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
  return res.json()
}

export async function deleteWebhook(webhookId: string): Promise<void> {
  const res = await authFetch(`/v1/auth/me/webhooks/${webhookId}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok && res.status !== 204) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
}

export async function listWebhookDeliveries(
  webhookId: string,
  page = 1,
  pageSize = 20,
): Promise<WebhookDeliveryList> {
  const res = await authFetch(
    `/v1/auth/me/webhooks/${webhookId}/deliveries?page=${page}&page_size=${pageSize}`,
  )
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
  return res.json()
}

export async function testWebhook(webhookId: string): Promise<{ message: string }> {
  const res = await authFetch(`/v1/auth/me/webhooks/${webhookId}/test`, {
    method: "POST",
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Request failed ${res.status}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Chunked Upload API (US-3.1 AC-4)
// ---------------------------------------------------------------------------

const CHUNK_SIZE = 5 * 1024 * 1024 // 5 MB

export interface ChunkedUploadSession {
  upload_id: string
  chunk_size: number
  total_chunks: number
  expires_at: string
}

export interface ChunkedUploadProgress {
  upload_id: string
  total_chunks: number
  uploaded_chunks: number[]
  status: string
}

/**
 * POST /upload/init — start a chunked upload session.
 * Returns upload session metadata including the upload_id for subsequent chunk calls.
 */
export async function initChunkedUpload(
  filename: string,
  fileSize: number,
  sourceLang: string,
  targetLang: string,
  glossaryId?: string,
  trackedChangesAction?: string,
  isScannedOverride?: boolean,
): Promise<ChunkedUploadSession> {
  const body = {
    filename,
    file_size: fileSize,
    source_lang: sourceLang,
    target_lang: targetLang,
    ...(glossaryId ? { glossary_id: glossaryId } : {}),
    ...(trackedChangesAction ? { tracked_changes_action: trackedChangesAction } : {}),
    ...(isScannedOverride !== undefined ? { is_scanned_override: isScannedOverride } : {}),
  }
  const res = await authFetch("/v1/upload/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const msg = typeof json?.detail === "string"
      ? json.detail
      : json?.detail?.message ?? `Upload init failed: ${res.status}`
    throw Object.assign(new Error(msg), { status: res.status, body: json })
  }
  return res.json()
}

/**
 * POST /upload/{id}/chunks/{n} — upload one chunk.
 * Returns updated progress.
 * Safe to retry — if chunk already received, returns OK idempotently.
 */
export async function uploadChunk(
  uploadId: string,
  chunkIndex: number,
  chunk: Blob,
): Promise<ChunkedUploadProgress> {
  const res = await authFetch(`/v1/upload/${uploadId}/chunks/${chunkIndex}`, {
    method: "POST",
    body: chunk,
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const msg = typeof json?.detail === "string"
      ? json.detail
      : json?.detail?.message ?? `Chunk upload failed: ${res.status}`
    throw Object.assign(new Error(msg), { status: res.status, body: json })
  }
  return res.json()
}

/**
 * GET /upload/{id}/status — poll upload progress.
 */
export async function getChunkedUploadStatus(
  uploadId: string,
): Promise<ChunkedUploadProgress> {
  const res = await authFetch(`/v1/upload/${uploadId}/status`, {
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Status check failed: ${res.status}`)
  }
  return res.json()
}

/**
 * POST /upload/{id}/complete — assemble chunks and start translation.
 * Returns {job_id, has_tracked_changes, is_scanned}.
 */
export async function completeChunkedUpload(
  uploadId: string,
): Promise<{ job_id: string; has_tracked_changes: boolean; is_scanned: boolean }> {
  const res = await authFetch(`/v1/upload/${uploadId}/complete`, {
    method: "POST",
    throwOnError: false,
  })
  if (!res.ok) {
    const json = await res.json().catch(() => null)
    const msg = typeof json?.detail === "string"
      ? json.detail
      : json?.detail?.message ?? `Complete upload failed: ${res.status}`
    throw Object.assign(new Error(msg), { status: res.status, body: json })
  }
  return res.json()
}

/**
 * DELETE /upload/{id} — cancel an active upload session.
 */
export async function cancelChunkedUpload(uploadId: string): Promise<void> {
  const res = await authFetch(`/v1/upload/${uploadId}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok && res.status !== 204) {
    const json = await res.json().catch(() => null)
    throw new Error(json?.detail ?? `Cancel upload failed: ${res.status}`)
  }
}

/**
 * Full chunked upload flow with progress reporting.
 *
 * Splits file into 5 MB chunks, uploads sequentially, calls complete when done.
 * onProgress(bytesUploaded, totalBytes) is called after each chunk.
 * onError(error) is called on failure; caller should call cancelChunkedUpload() to clean up.
 *
 * Returns { job_id } on success.
 */
export async function chunkedUploadWithProgress(
  file: File,
  sourceLang: string,
  targetLang: string,
  options: {
    glossaryId?: string
    trackedChangesAction?: string
    isScannedOverride?: boolean
    onProgress?: (uploadedBytes: number, totalBytes: number) => void
    onError?: (err: Error) => void
  } = {},
): Promise<{ job_id: string; has_tracked_changes: boolean; is_scanned: boolean }> {
  const {
    glossaryId,
    trackedChangesAction,
    isScannedOverride,
    onProgress,
    onError,
  } = options

  let uploadId: string | null = null

  try {
    // Step 1: Init
    const init = await initChunkedUpload(
      file.name,
      file.size,
      sourceLang,
      targetLang,
      glossaryId,
      trackedChangesAction,
      isScannedOverride,
    )
    uploadId = init.upload_id

    // Step 2: Upload chunks
    const totalChunks = init.total_chunks
    let uploadedBytes = 0

    for (let i = 0; i < totalChunks; i++) {
      const start = i * init.chunk_size
      const end = Math.min(start + init.chunk_size, file.size)
      const chunk = file.slice(start, end)

      // eslint-disable-next-line no-await-in-loop
      await uploadChunk(uploadId, i, chunk)

      uploadedBytes = end
      onProgress?.(uploadedBytes, file.size)
    }

    // Step 3: Complete
    const result = await completeChunkedUpload(uploadId)
    return result
  } catch (err) {
    // Clean up on error
    if (uploadId) {
      cancelChunkedUpload(uploadId).catch(() => {})
    }
    onError?.(err as Error)
    throw err
  }
}
