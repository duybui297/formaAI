"use client"
import { CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { JobStage } from "@/lib/types"

const STAGES: Array<{ key: string; label: string }> = [
  { key: "parse", label: "Parse" },
  { key: "translate", label: "Translate" },
  { key: "reassemble", label: "Reassemble" },
  { key: "done", label: "Done" },
]

const STAGE_ORDER: Record<string, number> = {
  parse: 0,
  translate: 1,
  reassemble: 2,
  done: 3,
  failed: 3,
}

interface StageIndicatorProps {
  stage: JobStage
}

export function StageIndicator({ stage }: StageIndicatorProps) {
  const activeIdx = STAGE_ORDER[stage] ?? 0
  const isFailed = stage === "failed"

  return (
    <div
      className="flex items-start gap-0 w-full"
      role="list"
      aria-label="Translation stages"
    >
      {STAGES.map(({ key, label }, idx) => {
        const isPast = idx < activeIdx
        const isActive = idx === activeIdx
        const isFuture = idx > activeIdx

        return (
          <div key={key} className="flex items-center flex-1 last:flex-none">
            <div
              className="flex flex-col items-center gap-1"
              role="listitem"
              aria-current={isActive ? "step" : undefined}
            >
              <div
                className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center",
                  isPast && "bg-emerald-500",
                  isActive && !isFailed && "bg-indigo-600",
                  isActive && isFailed && "bg-red-600",
                  isFuture && "bg-slate-300"
                )}
              >
                {isPast && <CheckCircle2 className="w-4 h-4 text-white" />}
                {isActive && !isFailed && (
                  <div className="w-2 h-2 bg-white rounded-full" />
                )}
                {isActive && isFailed && (
                  <XCircle className="w-4 h-4 text-white" />
                )}
              </div>
              <span
                className={cn(
                  "text-xs",
                  isPast && "text-emerald-600",
                  isActive && !isFailed && "text-indigo-600 font-semibold",
                  isActive && isFailed && "text-red-600 font-semibold",
                  isFuture && "text-slate-400"
                )}
              >
                {label}
              </span>
            </div>
            {idx < STAGES.length - 1 && (
              <div
                className={cn(
                  "flex-1 border-t mb-4",
                  idx < activeIdx ? "border-emerald-400" : "border-slate-200"
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
