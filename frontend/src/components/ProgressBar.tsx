import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

interface ProgressBarProps {
  value: number // 0-100
  className?: string
}

export function ProgressBar({ value, className }: ProgressBarProps) {
  return (
    <Progress
      value={value}
      className={cn("h-2 [&>div]:bg-indigo-500", className)}
      aria-label="Translation progress"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    />
  )
}
