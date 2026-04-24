"use client"
import { useState } from "react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Button } from "@/components/ui/button"
import { ChevronDown } from "lucide-react"
import type { JobProgress } from "@/lib/types"

interface ErrorDetailsProps {
  error: NonNullable<JobProgress["error"]>
  lastMessage: string
}

export function ErrorDetails({ error, lastMessage }: ErrorDetailsProps) {
  const [open, setOpen] = useState(false)

  return (
    <Alert variant="destructive" className="mt-4">
      <AlertTitle>Translation Failed</AlertTitle>
      <AlertDescription className="mt-2 space-y-2">
        <p>
          {error.message || lastMessage}. Check the details below or try again.
        </p>
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
