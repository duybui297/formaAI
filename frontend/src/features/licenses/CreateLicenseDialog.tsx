"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { createLicense } from "@/lib/api"
import type { LicenseTier } from "@/lib/types"

interface CreateLicenseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (rawKey: string) => void
}

export function CreateLicenseDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateLicenseDialogProps) {
  const queryClient = useQueryClient()

  const [tier, setTier] = useState<LicenseTier>("starter")
  const [customerId, setCustomerId] = useState("")
  const [maxDevices, setMaxDevices] = useState("1")
  const [expiredAt, setExpiredAt] = useState("")

  const mutation = useMutation({
    mutationFn: () =>
      createLicense({
        tier,
        customer_id: customerId || undefined,
        max_devices: Number(maxDevices) || 1,
        expired_at: expiredAt || undefined,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["licenses"] })
      onOpenChange(false)
      onCreated(data.raw_key)
      // reset
      setTier("starter")
      setCustomerId("")
      setMaxDevices("1")
      setExpiredAt("")
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    mutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="create-license-dialog">
        <DialogHeader>
          <DialogTitle className="font-montserrat">Create License</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="tier">Tier</Label>
            <Select value={tier} onValueChange={(v) => setTier(v as LicenseTier)}>
              <SelectTrigger id="tier" data-testid="tier-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="starter">Starter</SelectItem>
                <SelectItem value="professional">Professional</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="customer_id">Customer ID</Label>
            <Input
              id="customer_id"
              data-testid="customer-id-input"
              placeholder="e.g. customer@company.com"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="max_devices">Max devices</Label>
            <Input
              id="max_devices"
              data-testid="max-devices-input"
              type="number"
              min={1}
              value={maxDevices}
              onChange={(e) => setMaxDevices(e.target.value)}
            />
          </div>

          {tier === "enterprise" && (
            <div className="space-y-1.5">
              <Label htmlFor="expired_at">Custom expiry date</Label>
              <Input
                id="expired_at"
                data-testid="expired-at-input"
                type="date"
                value={expiredAt}
                onChange={(e) => setExpiredAt(e.target.value)}
              />
            </div>
          )}

          {mutation.isError && (
            <p className="text-sm text-red-600">
              {(mutation.error as Error).message}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              data-testid="create-license-submit"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Creating…" : "Create License"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
