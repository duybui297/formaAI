"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { getLicenseActivities, extendExpiry } from "@/lib/api"
import type { License, LicenseActivity } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useCrudToast } from "@/hooks/use-crud-toast"

const ACTION_COLORS: Record<string, string> = {
  created: "bg-sky-400",
  activated: "bg-emerald-400",
  suspended: "bg-orange-400",
  revoked: "bg-red-400",
  extended: "bg-violet-400",
}

function ActivityTimeline({ activities }: { activities: LicenseActivity[] }) {
  if (activities.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No activity yet.
      </p>
    )
  }

  return (
    <ol
      data-testid="activity-timeline"
      className="relative border-l border-border ml-2 space-y-4"
    >
      {activities.map((act) => (
        <li key={act.id} className="ml-4">
          <span
            className={cn(
              "absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white",
              ACTION_COLORS[act.action] ?? "bg-muted"
            )}
          />
          <p className="text-xs text-muted-foreground">
            {new Date(act.created_at).toLocaleString()}
            {act.actor ? ` · ${act.actor}` : ""}
          </p>
          <p className="text-sm text-foreground font-medium capitalize">
            {act.action}
          </p>
          {act.detail && (
            <p className="text-xs text-muted-foreground">{act.detail}</p>
          )}
        </li>
      ))}
    </ol>
  )
}

interface LicenseDetailDrawerProps {
  license: License | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function LicenseDetailDrawer({
  license,
  open,
  onOpenChange,
}: LicenseDetailDrawerProps) {
  const queryClient = useQueryClient()
  const crud = useCrudToast()
  const [extendDate, setExtendDate] = useState("")
  const [showExtend, setShowExtend] = useState(false)

  const { data: activities = [] } = useQuery<LicenseActivity[]>({
    queryKey: ["license-activities", license?.id],
    queryFn: () => getLicenseActivities(license!.id),
    enabled: !!license && open,
  })

  const extendMutation = useMutation({
    mutationFn: () => extendExpiry(license!.id, extendDate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["licenses"] })
      crud.extended("License", license?.key_masked)
      setShowExtend(false)
      setExtendDate("")
    },
    onError: (err: Error) => {
      crud.failed("extend", "license", err)
    },
  })

  if (!license) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg max-h-[80vh] flex flex-col"
        data-testid="license-detail-drawer"
      >
        <DialogHeader>
          <DialogTitle className="font-montserrat text-base">
            License Detail
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {/* Key info */}
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Key</span>
              <span className="font-mono text-foreground">{license.key_masked}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tier</span>
              <span className="text-foreground capitalize">{license.tier}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              <span className="text-foreground capitalize">{license.status}</span>
            </div>
            {license.customer_id && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Customer</span>
                <span className="text-foreground">{license.customer_id}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Issued</span>
              <span className="text-foreground">
                {new Date(license.issued_at).toLocaleDateString()}
              </span>
            </div>
            {license.expired_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Expires</span>
                <span className="text-foreground">
                  {new Date(license.expired_at).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>

          <Separator />

          {/* Extend expiry */}
          <div>
            <Button
              variant="outline"
              size="sm"
              data-testid="extend-expiry-button"
              onClick={() => setShowExtend((v) => !v)}
            >
              Extend Expiry
            </Button>

            {showExtend && (
              <div className="mt-3 space-y-2" data-testid="extend-expiry-form">
                <Label htmlFor="extend-date" className="text-sm">New expiry date</Label>
                <div className="flex gap-2">
                  <Input
                    id="extend-date"
                    data-testid="extend-date-input"
                    type="date"
                    className="h-8 text-sm"
                    value={extendDate}
                    onChange={(e) => setExtendDate(e.target.value)}
                  />
                  <Button
                    size="sm"
                    data-testid="extend-expiry-submit"
                    disabled={!extendDate || extendMutation.isPending}
                    onClick={() => extendMutation.mutate()}
                  >
                    {extendMutation.isPending ? "Saving…" : "Save"}
                  </Button>
                </div>
                {extendMutation.isError && (
                  <p className="text-xs text-red-600">
                    {(extendMutation.error as Error).message}
                  </p>
                )}
              </div>
            )}
          </div>

          <Separator />

          {/* Activity timeline */}
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-3">Activity</h3>
            <ActivityTimeline activities={activities} />
          </div>
        </div>

        <DialogFooter className="pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
