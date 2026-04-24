"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"

export type TrackedChangesAction = "strip" | "preserve" | "cancel"

interface TrackedChangesModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Called with "strip" or "preserve" when user picks a non-cancel action */
  onApply: (action: "strip" | "preserve") => void
  /** Called when user picks cancel (either radio or Cancel Upload button) */
  onCancel: () => void
}

export function TrackedChangesModal({
  open,
  onOpenChange,
  onApply,
  onCancel,
}: TrackedChangesModalProps) {
  const [selection, setSelection] = useState<TrackedChangesAction>("strip")

  function handleApply() {
    if (selection === "cancel") {
      onCancel()
      return
    }
    onApply(selection as "strip" | "preserve")
  }

  return (
    <Dialog
      open={open}
      onOpenChange={open2 => {
        if (!open2) onCancel() // Dialog dismissed via Escape or overlay click → cancel
        onOpenChange(open2)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tracked Changes Detected</DialogTitle>
          <DialogDescription>
            This document has unresolved tracked changes. How would you like to handle them?
          </DialogDescription>
        </DialogHeader>
        <RadioGroup
          value={selection}
          onValueChange={v => setSelection(v as TrackedChangesAction)}
          className="flex flex-col gap-3 my-4"
        >
          <div className="flex items-start gap-3">
            <RadioGroupItem value="strip" id="tc-strip" className="mt-0.5" />
            <Label htmlFor="tc-strip" className="cursor-pointer font-normal">
              <div className="font-medium text-sm">
                Remove tracked changes before translating
              </div>
              <div className="text-sm text-slate-500">
                Insertions and deletions will be stripped. The final accepted text will be
                translated.
              </div>
            </Label>
          </div>
          <div className="flex items-start gap-3">
            <RadioGroupItem value="preserve" id="tc-preserve" className="mt-0.5" />
            <Label htmlFor="tc-preserve" className="cursor-pointer font-normal">
              <div className="font-medium text-sm">
                Preserve and translate both versions
              </div>
              <div className="text-sm text-slate-500">
                Inserted and deleted text will both be translated and kept in the output
                document.
              </div>
            </Label>
          </div>
          <div className="flex items-start gap-3">
            <RadioGroupItem value="cancel" id="tc-cancel" className="mt-0.5" />
            <Label htmlFor="tc-cancel" className="cursor-pointer font-normal">
              <div className="font-medium text-sm">
                Cancel &mdash; I&apos;ll clean up the document first
              </div>
              <div className="text-sm text-slate-500">
                The upload will be cancelled so you can accept or reject the changes in
                Word.
              </div>
            </Label>
          </div>
        </RadioGroup>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel Upload
          </Button>
          <Button onClick={handleApply}>Apply Selection</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
