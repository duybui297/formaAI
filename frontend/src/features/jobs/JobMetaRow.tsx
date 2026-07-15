import { Badge } from "@/components/ui/badge"
import type { JobProgress } from "@/lib/types"

interface JobMetaRowProps {
  job: JobProgress
}

function formatAge(isoString?: string): string {
  if (!isoString) return ""
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return "just now"
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  return `${Math.floor(diffH / 24)}d ago`
}

export function JobMetaRow({ job }: JobMetaRowProps) {
  const sourceLang =
    job.source_lang === "auto"
      ? (job.detected_lang ?? "Auto")
      : (job.source_lang ?? "—")

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
      {job.source_lang && job.target_lang && (
        <span>
          {sourceLang} → {job.target_lang}
        </span>
      )}
      {job.input_format && (
        <Badge variant="outline" className="text-xs text-foreground">
          {job.input_format.toUpperCase()}
        </Badge>
      )}
      {job.created_at && <span>·</span>}
      {job.created_at && <span>{formatAge(job.created_at)}</span>}
    </div>
  )
}
