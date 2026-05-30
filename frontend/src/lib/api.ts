import type {
  Language,
  JobProgress,
  JobSummary,
  License,
  LicenseActivity,
  LicensesListParams,
  LicensesListResponse,
  CreateLicenseRequest,
  CreateLicenseResponse,
  ActivateLicenseRequest,
  ActivateLicenseResponse,
  ActivateLicenseError,
  CheckoutPlan,
  CheckoutLicenseResponse,
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
  const body: ActivateLicenseRequest = { key }
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
