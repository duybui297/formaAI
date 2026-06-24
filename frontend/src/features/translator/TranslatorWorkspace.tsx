"use client"
import { useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import {
  FileText,
  Download,
  Eye,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
  Lock,
} from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { UploadForm } from "@/features/upload/UploadForm"
import { ProgressBar } from "@/features/jobs/ProgressBar"
import { StageIndicator } from "@/features/jobs/StageIndicator"
import { ErrorDetails } from "@/features/jobs/ErrorDetails"
import { JobMetaRow } from "@/features/jobs/JobMetaRow"
import { useJobProgress } from "@/hooks/useJobProgress"
import { useCounterAnimation } from "@/hooks/useCounterAnimation"
import { useEntitlement } from "@/hooks/useEntitlement"
import { listJobs } from "@/lib/api"
import type { PaginatedJobsResponse } from "@/lib/types"
import { cn } from "@/lib/utils"
import type { JobStatus, JobSummary } from "@/lib/types"

const TERMINAL = new Set<JobStatus>(["done", "failed", "needs_review"])

function StatusDot({ status }: { status: JobStatus }) {
  return (
    <span
      className={cn(
        "px-2.5 py-1 rounded-full text-xs font-medium inline-flex items-center gap-1.5",
        status === "done" && "bg-emerald-50 text-emerald-700 border border-emerald-100",
        status === "needs_review" && "bg-amber-50 text-amber-700 border border-amber-100",
        status === "failed" && "bg-red-50 text-red-700 border border-red-100",
        status === "processing" && "bg-indigo-50 text-indigo-700 border border-indigo-100",
        status === "queued" && "bg-zinc-50 text-zinc-600 border border-zinc-200"
      )}
    >
      <div
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          status === "done" && "bg-emerald-500",
          status === "needs_review" && "bg-amber-500",
          status === "failed" && "bg-red-500",
          status === "processing" && "bg-indigo-500 animate-pulse",
          status === "queued" && "bg-zinc-400"
        )}
      />
      {status === "needs_review" ? "Review" : status}
    </span>
  )
}

function JobProgressCard({ jobId, onClose }: { jobId: string; onClose: () => void }) {
  const { data: job, isLoading } = useJobProgress(jobId)
  const isTerminal = job ? TERMINAL.has(job.status) : false
  const displayCount = useCounterAnimation(job?.segments_done ?? 0, isTerminal ? 0 : 300)

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6 space-y-4">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-2 w-full" />
      </div>
    )
  }

  if (!job) return null

  const progressPct =
    job.segments_total > 0
      ? Math.round((job.segments_done / job.segments_total) * 100)
      : job.status === "done" ? 100 : 0

  const isProcessing = job.status === "processing" || job.status === "queued"
  const isDone = job.status === "done" || job.status === "needs_review"

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold text-zinc-900 flex items-center gap-2">
          {isProcessing && <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />}
          {isDone && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
          {job.status === "failed" && <AlertCircle className="w-5 h-5 text-red-500" />}
          {isProcessing ? "Translating Document..." : isDone ? "Translation Complete" : "Translation Failed"}
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-zinc-500">{progressPct}%</span>
          <button onClick={onClose} className="p-1 text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 rounded-md transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="h-2 bg-zinc-100 rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            isDone ? "bg-emerald-500" : job.status === "failed" ? "bg-red-400" : "bg-indigo-600"
          )}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {isProcessing && (
        <div className="mt-4 bg-zinc-900 rounded-lg p-3 text-xs font-mono text-emerald-400 h-32 overflow-y-auto">
          <p>{">"} Analyzing document structure...</p>
          {progressPct > 10 && <p>{">"} Extracting text blocks and tables...</p>}
          {progressPct > 30 && <p>{">"} Translating content ({displayCount}/{job.segments_total} segments)...</p>}
          {progressPct > 60 && <p>{">"} Preserving typography and layout constraints...</p>}
          {progressPct > 85 && <p>{">"} Recompiling final document...</p>}
        </div>
      )}

      {job.status === "failed" && job.error && (
        <div className="mt-4">
          <ErrorDetails error={job.error} lastMessage={job.last_message} />
        </div>
      )}

      {isDone && (
        <div className="mt-6 flex gap-3">
          <Link
            href={`/jobs/${jobId}/review`}
            className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 text-white px-4 py-2.5 rounded-lg font-medium hover:bg-indigo-700 transition"
          >
            <Eye className="w-4 h-4" />
            Review Translation
          </Link>
          <button
            onClick={() => { window.location.href = `/api/v1/jobs/${jobId}/download` }}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium text-zinc-700 bg-white border border-zinc-200 hover:bg-zinc-50 transition"
          >
            <Download className="w-4 h-4" />
            Download
          </button>
        </div>
      )}
    </div>
  )
}

export function TranslatorWorkspace() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

  const { data: entitlement, isLoading: entitlementLoading } = useEntitlement()

  const { data: jobsData = { jobs: [] }, isLoading: jobsLoading } = useQuery<PaginatedJobsResponse>({
    queryKey: ["jobs-recent"],
    queryFn: () => listJobs({ page: 1, page_size: 10 }),
    refetchInterval: 5_000,
  })

  const isBlocked = !entitlementLoading && entitlement != null && !entitlement.has_active

  return (
    <div className="overflow-y-auto h-full p-6 md:p-8 lg:p-10">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Upload &amp; Translate</h1>
          <p className="text-zinc-500 mt-1">Translate documents with perfect formatting preservation.</p>
        </div>

        {/* License gate — blocked state */}
        {isBlocked && (
          <div
            className="bg-amber-50 border border-amber-200 rounded-2xl p-10 text-center space-y-4"
            data-testid="entitlement-blocked"
          >
            <div className="flex justify-center">
              <div className="w-14 h-14 bg-amber-100 rounded-full flex items-center justify-center">
                <Lock className="w-7 h-7 text-amber-600" />
              </div>
            </div>
            <h2 className="text-xl font-semibold text-zinc-900">License Required</h2>
            <p className="text-zinc-600 max-w-md mx-auto">
              You need an active license to translate documents. Choose a plan or activate an existing key.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <Link
                href="/pricing"
                className="inline-flex items-center justify-center gap-2 bg-indigo-600 text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-indigo-700 transition"
                data-testid="blocked-pricing-link"
              >
                Choose a plan
              </Link>
              <Link
                href="/activate"
                className="inline-flex items-center justify-center gap-2 bg-white border border-zinc-200 text-zinc-700 px-6 py-2.5 rounded-lg font-semibold hover:bg-zinc-50 transition"
                data-testid="blocked-activate-link"
              >
                Activate a key
              </Link>
            </div>
          </div>
        )}

        {/* Upload form — only when not blocked */}
        {!isBlocked && (
          <UploadForm
            onJobCreated={(id) => setSelectedJobId(id)}
            entitlement={entitlement}
          />
        )}

        {/* Active job progress */}
        {selectedJobId && (
          <JobProgressCard
            key={selectedJobId}
            jobId={selectedJobId}
            onClose={() => setSelectedJobId(null)}
          />
        )}

        {/* Recent translations */}
        <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-zinc-200 bg-zinc-50/50">
            <h3 className="text-sm font-semibold text-zinc-700 uppercase tracking-wider">
              Recent Translations
            </h3>
          </div>

          {jobsLoading ? (
            <div className="p-6 space-y-3">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : jobsData.jobs.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-sm font-medium text-zinc-500">No translations yet</p>
              <p className="text-xs text-zinc-400 mt-1">Upload a document to get started.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-zinc-50 border-b border-zinc-200 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                    <th className="px-6 py-3">File Name</th>
                    <th className="px-6 py-3">Language Pair</th>
                    <th className="px-6 py-3">Format</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200">
                  {jobsData.jobs.slice(0, 10).map((job) => (
                    <tr
                      key={job.id}
                      className="hover:bg-zinc-50/80 transition group cursor-pointer"
                      onClick={() => setSelectedJobId(job.id)}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                            <FileText className="w-4 h-4" />
                          </div>
                          <p className="text-sm font-medium text-zinc-900 truncate max-w-[200px]">
                            {job.original_filename}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="bg-zinc-100 px-2 py-1 rounded text-xs font-medium text-zinc-600">
                            {job.source_lang === "auto" ? "Auto" : job.source_lang}
                          </span>
                          <span className="text-zinc-400">&rarr;</span>
                          <span className="bg-indigo-50 px-2 py-1 rounded text-xs font-medium text-indigo-700">
                            {job.target_lang}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="bg-zinc-100 px-2 py-1 rounded text-xs font-medium text-zinc-600 uppercase">
                          {job.input_format}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <StatusDot status={job.status} />
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition" onClick={(e) => e.stopPropagation()}>
                          {(job.status === "done" || job.status === "needs_review") && (
                            <>
                              <Link
                                href={`/jobs/${job.id}/review`}
                                className="p-1.5 text-zinc-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition"
                                title="Review"
                              >
                                <Eye className="w-4 h-4" />
                              </Link>
                              <a
                                href={`/api/v1/jobs/${job.id}/download`}
                                className="p-1.5 text-zinc-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-md transition"
                                title="Download"
                              >
                                <Download className="w-4 h-4" />
                              </a>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
