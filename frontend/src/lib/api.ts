import type {
  Language,
  JobProgress,
  JobSummary,
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
  const res = await apiFetch("/languages")
  const data = await res.json()
  return data.languages as Language[]
}

export async function getGlossaries(): Promise<Glossary[]> {
  const res = await apiFetch("/glossaries")
  const data = await res.json()
  return data.glossaries as Glossary[]
}

export async function getJob(jobId: string): Promise<JobProgress> {
  const res = await apiFetch(`/jobs/${jobId}`)
  return res.json()
}

export async function listJobs(): Promise<JobSummary[]> {
  const res = await apiFetch("/jobs")
  const data = await res.json()
  return data.jobs as JobSummary[]
}

export interface CreateJobOptions {
  file: File
  source_lang: string
  target_lang: string
}

export async function createJob(options: CreateJobOptions): Promise<{ job_id: string; has_tracked_changes: boolean }> {
  const form = new FormData()
  form.append("file", options.file)
  form.append("source_lang", options.source_lang)
  form.append("target_lang", options.target_lang)

  const res = await authFetch("/jobs", {
    method: "POST",
    body: form,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`Upload failed ${res.status}: ${text}`)
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
  const res = await apiFetch(`/admin/licenses${query ? `?${query}` : ""}`)
  return res.json()
}

export async function createLicense(body: CreateLicenseRequest): Promise<CreateLicenseResponse> {
  const res = await apiFetch("/admin/licenses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function getLicense(id: string): Promise<License> {
  const res = await apiFetch(`/admin/licenses/${id}`)
  return res.json()
}

export async function getLicenseActivities(id: string): Promise<LicenseActivity[]> {
  const res = await apiFetch(`/admin/licenses/${id}/activities`)
  return res.json()
}

export async function suspendLicenses(ids: string[]): Promise<void> {
  await apiFetch("/admin/licenses/suspend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  })
}

export async function revokeLicenses(ids: string[]): Promise<void> {
  await apiFetch("/admin/licenses/revoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  })
}

export async function extendExpiry(id: string, expired_at: string): Promise<License> {
  const res = await apiFetch(`/admin/licenses/${id}/extend`, {
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
  const res = await authFetch("/licenses/activate", {
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
  const res = await authFetch("/licenses/checkout", {
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
  const res = await apiFetch(`/admin/users${query ? `?${query}` : ""}`)
  return res.json()
}

export async function createUser(body: CreateAdminUserRequest): Promise<AdminUser> {
  const res = await authFetch("/admin/users", {
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
  const res = await authFetch(`/admin/users/${id}`, {
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
  const res = await authFetch(`/admin/users/${id}`, {
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
  const res = await authFetch("/licenses/me", { throwOnError: false })
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
  const res = await authFetch("/licenses/my-licenses")
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
  const res = await apiFetch("/notifications")
  return res.json()
}

/**
 * PATCH /auth/me — update the current user's full_name.
 */
export async function updateMe(body: UpdateMeRequest): Promise<import("@/lib/types").AdminUser> {
  const res = await authFetch("/auth/me", {
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
  const res = await authFetch("/auth/me/avatar", {
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
  const res = await authFetch("/auth/me/password", {
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
  const res = await authFetch("/auth/me/notifications")
  return res.json()
}

export async function updateNotificationPreferences(
  patch: Partial<NotificationPreferences>
): Promise<NotificationPreferences> {
  const res = await authFetch("/auth/me/notifications", {
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
  const res = await authFetch("/auth/me/translation-defaults")
  return res.json()
}

export async function updateTranslationDefaults(
  patch: Partial<TranslationDefaults>
): Promise<TranslationDefaults> {
  const res = await authFetch("/auth/me/translation-defaults", {
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
  const res = await authFetch("/auth/me/api-keys")
  return res.json()
}

export async function createApiKey(name: string): Promise<ApiKeyCreated> {
  const res = await authFetch("/auth/me/api-keys", {
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
  const res = await authFetch(`/auth/me/api-keys/${keyId}`, {
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
  const res = await authFetch("/auth/me/workspace")
  return res.json()
}

export async function inviteMember(email: string, role: string): Promise<WorkspaceInvite> {
  const res = await authFetch("/auth/me/workspace/invite", {
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
  const res = await authFetch(`/auth/me/workspace/invite/${inviteId}`, {
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
  const res = await authFetch(`/auth/me/workspace/member/${memberId}`, {
    method: "DELETE",
    throwOnError: false,
  })
  if (!res.ok && res.status !== 204) {
    const json = await res.json().catch(() => null)
    const detail = json?.detail ?? json?.message ?? `Request failed ${res.status}`
    throw new Error(detail)
  }
}
