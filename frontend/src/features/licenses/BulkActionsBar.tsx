"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { suspendLicenses, revokeLicenses } from "@/lib/api"
import { PauseCircle, XCircle } from "lucide-react"

interface BulkActionsBarProps {
  selectedIds: Set<string>
  onClearSelection: () => void
}

export function BulkActionsBar({ selectedIds, onClearSelection }: BulkActionsBarProps) {
  const queryClient = useQueryClient()
  const count = selectedIds.size

  const suspendMutation = useMutation({
    mutationFn: () => suspendLicenses(Array.from(selectedIds)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["licenses"] })
      onClearSelection()
    },
  })

  const revokeMutation = useMutation({
    mutationFn: () => revokeLicenses(Array.from(selectedIds)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["licenses"] })
      onClearSelection()
    },
  })

  if (count === 0) return null

  const isPending = suspendMutation.isPending || revokeMutation.isPending

  return (
    <div
      data-testid="bulk-actions-bar"
      className="flex items-center gap-3 px-4 py-2.5 bg-indigo-50 border border-indigo-200 rounded-lg text-sm"
    >
      <span className="text-indigo-700 font-medium">
        {count} selected
      </span>

      <Button
        variant="outline"
        size="sm"
        data-testid="bulk-suspend"
        disabled={isPending}
        onClick={() => suspendMutation.mutate()}
        className="h-7 gap-1.5 text-orange-700 border-orange-300 hover:bg-orange-50"
      >
        <PauseCircle className="w-3.5 h-3.5" />
        Suspend
      </Button>

      <Button
        variant="outline"
        size="sm"
        data-testid="bulk-revoke"
        disabled={isPending}
        onClick={() => {
          if (window.confirm(`Revoke ${count} license(s)? This cannot be undone.`)) {
            revokeMutation.mutate()
          }
        }}
        className="h-7 gap-1.5 text-red-700 border-red-300 hover:bg-red-50"
      >
        <XCircle className="w-3.5 h-3.5" />
        Revoke
      </Button>

      <button
        data-testid="bulk-clear"
        className="ml-auto text-xs text-zinc-400 hover:text-zinc-600"
        onClick={onClearSelection}
      >
        Clear
      </button>
    </div>
  )
}
