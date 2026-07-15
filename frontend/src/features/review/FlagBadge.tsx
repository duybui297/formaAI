"use client"
import { Badge } from "@/components/ui/badge"
import type { FlagType } from "@/lib/types"

const FLAG_CONFIG: Record<FlagType, { label: string; className: string }> = {
  overflow:             { label: "Overflow",   className: "text-amber-600 bg-amber-50 border-amber-200" },
  glossary_violation:   { label: "Glossary",   className: "text-violet-700 bg-violet-50 border-violet-200" },
  placeholder_mismatch: { label: "Placeholder",className: "text-orange-700 bg-orange-50 border-orange-200" },
  llm_refusal:          { label: "Refusal",    className: "text-red-700 bg-red-50 border-red-200" },
  smartart:             { label: "SMART",      className: "text-orange-700 bg-orange-50 border-orange-200" },
  multi_column_degraded:{ label: "MULTI-COL",  className: "text-muted-foreground bg-muted border-input" },
  // Phase 4 additions (D-04-24, D-04-31)
  figure_passthrough:   { label: "FIGURE",     className: "text-muted-foreground bg-muted border-border" },
  ocr_page_error:       { label: "OCR ERR",    className: "text-amber-700 bg-amber-50 border-amber-200" },
}

// M2: overflow + auto_adjusted=true renders as informational AUTO-FIT badge (not warning)
const AUTO_FIT_CONFIG = { label: "AUTO-FIT", className: "text-muted-foreground bg-muted border-input" }

interface FlagBadgeProps {
  flagType: FlagType
  details?: Record<string, unknown> | null
  className?: string
}

export function FlagBadge({ flagType, details, className }: FlagBadgeProps) {
  // M2: overflow with auto_adjusted=true → informational AUTO-FIT badge
  const config =
    flagType === "overflow" && details?.auto_adjusted === true
      ? AUTO_FIT_CONFIG
      : FLAG_CONFIG[flagType]

  return (
    <Badge
      variant="outline"
      className={`text-xs font-normal ${config.className} ${className ?? ""}`}
    >
      {config.label}
    </Badge>
  )
}
