import type { Language, JobProgress, JobSummary } from "@/lib/types"
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
