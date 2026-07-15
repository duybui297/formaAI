"use client"
import { useState } from "react"
import Link from "next/link"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import { ChevronDown, RefreshCw, Coins } from "lucide-react"
import type { FailureDetails, FailureReason, JobProgress } from "@/lib/types"

interface ErrorDetailsProps {
  error: NonNullable<JobProgress["error"]>
  lastMessage: string
  failureReason?: FailureReason | null
  failureDetails?: FailureDetails | null
}

// US-3.8: Human-readable labels for failure reasons
const FAILURE_LABELS: Record<FailureReason, { title: string; description: string; retryable: boolean }> = {
  unsupported_content: {
    title: "Unsupported Content",
    description: "The uploaded file contains content that could not be translated.",
    retryable: false,
  },
  ocr_low_confidence: {
    title: "Low OCR Quality",
    description: "The scanned document had too many unreadable sections.",
    retryable: true,
  },
  model_timeout: {
    title: "Server Timeout",
    description: "The translation service took too long and timed out.",
    retryable: true,
  },
  payment: {
    title: "Payment Error",
    description: "There was a billing issue with your account.",
    retryable: false,
  },
  quota_exceeded: {
    title: "Quota Exceeded",
    description: "You have reached your monthly translation limit.",
    retryable: false,
  },
  feature_not_in_plan: {
    title: "Feature Not in Plan",
    description: "This feature requires an upgrade to your plan.",
    retryable: false,
  },
  segment_too_large: {
    title: "Content Too Large",
    description: "A segment in your document exceeds the maximum size.",
    retryable: false,
  },
  translation_error: {
    title: "Translation Error",
    description: "An unexpected error occurred during translation.",
    retryable: true,
  },
}

export function ErrorDetails({ error, lastMessage, failureReason, failureDetails }: ErrorDetailsProps) {
  const [open, setOpen] = useState(false)

  const reasonInfo = failureReason ? FAILURE_LABELS[failureReason] : null
  const canRetry = reasonInfo?.retryable ?? false

  return (
    <Alert variant="destructive" className="mt-4">
      <AlertTitle>Translation Failed</AlertTitle>
      <AlertDescription className="mt-2 space-y-3">
        {reasonInfo ? (
          <>
            <p className="font-medium">{reasonInfo.title}</p>
            <p className="text-sm opacity-90">{reasonInfo.description}</p>
            {failureDetails?.message && (
              <p className="text-sm opacity-75">{failureDetails.message}</p>
            )}
          </>
        ) : (
          <p>
            {error.message || lastMessage}. Check the details below or try again.
          </p>
        )}

        {canRetry && (
          <div className="flex items-center gap-2 pt-2">
            <RefreshCw className="w-4 h-4" />
            <span className="text-sm">Free retry available within 24 hours.</span>
          </div>
        )}

        {error.failing_segments.length > 0 && (
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="text-red-700 hover:text-red-800 px-0"
              >
                {open ? "Hide details" : "Show failing segments"}
                <ChevronDown
                  className={`ml-1 h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2 space-y-2">
              {error.failing_segments.map((seg) => (
                <div
                  key={seg.id}
                  className="rounded bg-red-50 border border-red-200 p-3 text-sm text-red-900"
                >
                  <p className="font-mono text-xs text-red-500 mb-1">
                    segment {seg.id} · batch {seg.batch_id}
                  </p>
                  <p className="line-clamp-3">{seg.source_text}</p>
                </div>
              ))}
            </CollapsibleContent>
          </Collapsible>
        )}
      </AlertDescription>
    </Alert>
  )
}
