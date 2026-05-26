"use client"
import { use } from "react"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { StageIndicator } from "@/features/jobs/StageIndicator"
import { ProgressBar } from "@/features/jobs/ProgressBar"
import { ErrorDetails } from "@/features/jobs/ErrorDetails"
import { JobMetaRow } from "@/features/jobs/JobMetaRow"
import { useJobProgress } from "@/hooks/useJobProgress"
import { useCounterAnimation } from "@/hooks/useCounterAnimation"
import type { JobStatus } from "@/lib/types"

// Next.js 16 async params: unwrap with React.use() per D-20
export default function JobStatusPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: jobId } = use(params)
  const { data: job, isLoading } = useJobProgress(jobId)

  const TERMINAL = new Set<JobStatus>(["done", "failed", "needs_review"])
  const isTerminal = job ? TERMINAL.has(job.status) : false

  const displayCount = useCounterAnimation(
    job?.segments_done ?? 0,
    isTerminal ? 0 : 300
  )

  if (isLoading) {
    return (
      <>
        <main className="max-w-3xl mx-auto px-8 py-12 space-y-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-2 w-full" />
          <Skeleton className="h-4 w-48" />
        </main>
      </>
    )
  }

  if (!job) {
    return (
      <>
        <main className="max-w-3xl mx-auto px-8 py-12">
          <p className="text-slate-500 text-sm">
            Job not found.{" "}
            <Link href="/translator" className="underline">
              Back to jobs
            </Link>
          </p>
        </main>
      </>
    )
  }

  const progressPct =
    job.segments_total > 0
      ? Math.round((job.segments_done / job.segments_total) * 100)
      : job.status === "done"
        ? 100
        : 0

  return (
    <>
      <main className="max-w-3xl mx-auto px-8 py-12 space-y-6">
        {/* Back link */}
        <Link
          href="/translator"
          className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
        >
          <ArrowLeft className="h-4 w-4" />
          All Jobs
        </Link>

        {/* Heading */}
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {job.original_filename ?? jobId}
          </h1>
          <JobMetaRow job={job} />
        </div>

        {/* Stage indicator */}
        {job.stage && <StageIndicator stage={job.stage} />}

        {/* Progress section */}
        <div className="space-y-2">
          {job.status === "queued" ? (
            <>
              <Skeleton className="h-2 w-full" />
              <p className="text-sm text-slate-500">Waiting for worker...</p>
            </>
          ) : (
            <>
              <ProgressBar value={progressPct} />
              {job.segments_total > 0 && (
                <p className="text-sm text-slate-700">
                  {displayCount} / {job.segments_total} segments translated
                </p>
              )}
              {/* Retry chip — D-12: slate-500, no red, no background */}
              {job.retry_count > 0 && job.status === "running" && (
                <p className="text-xs text-slate-500 transition-opacity duration-150">
                  Retrying batch {job.current_batch} ({job.retry_count}/3)
                </p>
              )}
              {/* Detected language badge — D-16 */}
              {job.detected_lang && job.source_lang === "auto" && (
                <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200">
                  Detected: {job.detected_lang}
                </Badge>
              )}
            </>
          )}
        </div>

        {/* Error section — D-11 */}
        {job.status === "failed" && job.error && (
          <ErrorDetails error={job.error} lastMessage={job.last_message} />
        )}

        {/* Action section */}
        {job.status === "done" && (
          <div className="flex flex-col gap-3">
            <Button
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
              onClick={() => {
                window.location.href = `/api/jobs/${jobId}/download`
              }}
            >
              Download Translation
            </Button>
            <Link
              href={`/jobs/${jobId}/review`}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-violet-500 hover:bg-violet-600 text-white text-sm font-medium w-full"
            >
              Review Translation
            </Link>
          </div>
        )}

        {job.status === "needs_review" && (
          <div className="rounded-lg border border-slate-200 bg-white p-6 text-center space-y-3">
            <h2 className="text-base font-semibold text-slate-800">
              Review Required
            </h2>
            <p className="text-sm text-slate-500">
              Some segments were flagged for review. Open the review editor to
              inspect and edit translations before exporting.
            </p>
            <div className="flex flex-col gap-2">
              <Link
                href={`/jobs/${jobId}/review`}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-violet-500 hover:bg-violet-600 text-white text-sm font-medium w-full"
              >
                Review Translation
              </Link>
              <Button
                variant="outline"
                className="border-indigo-600 text-indigo-600 hover:bg-indigo-50 w-full"
                onClick={() => {
                  window.location.href = `/api/jobs/${jobId}/download`
                }}
              >
                Download Current Output
              </Button>
            </div>
          </div>
        )}
      </main>
    </>
  )
}
