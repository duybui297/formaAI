"use client"
import { use } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, RefreshCw, Coins } from "lucide-react"
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
  const router = useRouter()
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
          <p className="text-muted-foreground text-sm">
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
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          All Jobs
        </Link>

        {/* Heading */}
        <div>
          <h1 className="text-xl font-semibold text-foreground">
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
              <p className="text-sm text-muted-foreground">Waiting for worker...</p>
            </>
          ) : (
            <>
              <ProgressBar value={progressPct} />
              {job.segments_total > 0 && (
                <p className="text-sm text-foreground">
                  {displayCount} / {job.segments_total} segments translated
                </p>
              )}
              {/* Retry chip — D-12: slate-500, no red, no background */}
              {job.retry_count > 0 && job.status === "processing" && (
                <p className="text-xs text-muted-foreground transition-opacity duration-150">
                  Retrying batch {job.current_batch} ({job.retry_count}/3)
                </p>
              )}
              {/* Detected language badge — D-16 */}
              {job.detected_lang && job.source_lang === "auto" && (
                <Badge className="bg-primary/15 text-primary border-primary/20">
                  Detected: {job.detected_lang}
                </Badge>
              )}
            </>
          )}
        </div>

        {/* Error section — D-11 + US-3.8 */}
        {job.status === "failed" && job.error && (
          <ErrorDetails
            error={job.error}
            lastMessage={job.last_message}
            failureReason={job.failure_reason}
            failureDetails={job.failure_details}
          />
        )}

        {/* US-3.8: Retry action for failed jobs */}
        {job.status === "failed" && (
          <div className="rounded-xl border border-border bg-card p-6 space-y-3">
            <h3 className="font-semibold text-foreground">Translation Failed</h3>
            <p className="text-sm text-muted-foreground">
              This job could not be completed. You can retry from the upload page.
            </p>
            <div className="flex flex-col gap-2">
              {job.failure_reason &&
                ["model_timeout", "ocr_low_confidence", "translation_error"].includes(job.failure_reason) ? (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 text-sm text-emerald-700 dark:text-emerald-400">
                  <RefreshCw className="w-4 h-4 shrink-0" />
                  <span>Free retry available within 24 hours (credits refunded)</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 text-sm text-amber-700 dark:text-amber-400">
                  <Coins className="w-4 h-4 shrink-0" />
                  <span>Retry will use credits from your quota</span>
                </div>
              )}
              <Button
                variant="outline"
                className="w-full"
                onClick={() => router.push("/translator")}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry Translation
              </Button>
            </div>
          </div>
        )}

        {/* Action section */}
        {job.status === "done" && (
          <div className="flex flex-col gap-3">
            <Button
              className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
              onClick={() => {
                window.location.href = `/api/v1/jobs/${jobId}/download`
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
          <div className="rounded-lg border border-border bg-card p-6 text-center space-y-3">
            <h2 className="text-base font-semibold text-foreground">
              Review Required
            </h2>
            <p className="text-sm text-muted-foreground">
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
                className="border-primary text-primary hover:bg-primary/10 w-full"
                onClick={() => {
                  window.location.href = `/api/v1/jobs/${jobId}/download`
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
