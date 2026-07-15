"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { useCrudToast } from "@/hooks/use-crud-toast"
import { useConfirm } from "@/hooks/use-confirm"
import { suspendLicenses, revokeLicenses } from "@/lib/api"
import { PauseCircle, XCircle } from "lucide-react"

interface BulkActionsBarProps {
  selectedIds: Set<string>
  onClearSelection: () => void
}

export function BulkActionsBar({ selectedIds, onClearSelection }: BulkActionsBarProps) {
  const queryClient = useQueryClient()
  const crud = useCrudToast()
  const confirm = useConfirm()
  const count = selectedIds.size
  const ids = Array.from(selectedIds)

  const suspendMutation = useMutation({
    mutationFn: () => suspendLicenses(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["licenses"] })
      crud.suspended("Licenses", `${count} license${count !== 1 ? "s" : ""}`)
      onClearSelection()
    },
    onError: (err: Error) => {
      crud.failed("suspend", "licenses", err)
    },
  })

  const revokeMutation = useMutation({
    mutationFn: () => revokeLicenses(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["licenses"] })
      crud.revoked("Licenses", `${count} license${count !== 1 ? "s" : ""}`)
      onClearSelection()
    },
    onError: (err: Error) => {
      crud.failed("revoke", "licenses", err)
    },
  })

  if (count === 0) return null

  const isPending = suspendMutation.isPending || revokeMutation.isPending

  const handleRevoke = async () => {
    const ok = await confirm({
      title: `Revoke ${count} license${count !== 1 ? "s" : ""}?`,
      description: "Revoked licenses cannot be restored. This action cannot be undone.",
      confirmLabel: count !== 1 ? `Revoke all ${count}` : "Revoke",
      tone: "danger",
    })
    if (ok) revokeMutation.mutate()
  }

  return (
    <div
      data-testid="bulk-actions-bar"
      className="flex items-center gap-3 px-4 py-2.5 bg-primary/10 border border-primary/20 rounded-lg text-sm"
    >
      <span className="text-primary font-medium">
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
        onClick={handleRevoke}
        className="h-7 gap-1.5 text-red-700 border-red-300 hover:bg-red-50"
      >
        <XCircle className="w-3.5 h-3.5" />
        Revoke
      </Button>

      <button
        data-testid="bulk-clear"
        className="ml-auto text-xs text-muted-foreground hover:text-muted-foreground"
        onClick={onClearSelection}
      >
        Clear
      </button>
    </div>
  )
}
