import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { JobStatus } from "@/lib/types"

const STATUS_STYLES: Record<JobStatus, string> = {
  queued: "text-amber-500 border-amber-200 bg-amber-50",
  processing: "text-primary border-primary/20 bg-primary/10",
  needs_review: "text-amber-600 border-amber-300 bg-amber-50",
  failed: "text-red-600 border-red-200 bg-red-50",
  done: "text-emerald-600 border-emerald-200 bg-emerald-50",
}

const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "queued",
  processing: "processing",
  needs_review: "needs review",
  failed: "failed",
  done: "done",
}

interface StatusBadgeProps {
  status: JobStatus
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn("text-xs font-medium", STATUS_STYLES[status], className)}
    >
      {STATUS_LABELS[status]}
    </Badge>
  )
}
