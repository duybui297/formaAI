"use client"
import { Badge } from "@/components/ui/badge"
import type { FlagType } from "@/lib/types"

const FLAG_CONFIG: Record<FlagType, { label: string; className: string }> = {
  overflow:             { label: "Overflow",    className: "text-amber-600 bg-amber-50 border-amber-200" },
  glossary_violation:   { label: "Glossary",    className: "text-violet-700 bg-violet-50 border-violet-200" },
  placeholder_mismatch: { label: "Placeholder", className: "text-orange-700 bg-orange-50 border-orange-200" },
  llm_refusal:          { label: "Refusal",     className: "text-red-700 bg-red-50 border-red-200" },
}

interface FlagBadgeProps {
  flagType: FlagType
  className?: string
}

export function FlagBadge({ flagType, className }: FlagBadgeProps) {
  const config = FLAG_CONFIG[flagType]
  return (
    <Badge
      variant="outline"
      className={`text-xs font-normal ${config.className} ${className ?? ""}`}
    >
      {config.label}
    </Badge>
  )
}
