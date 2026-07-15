"use client"

import { useState } from "react"
import type { ReactNode } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Copy, Check } from "lucide-react"
import { useCrudToast } from "@/hooks/use-crud-toast"

interface OneTimeKeyDialogProps {
  open: boolean
  rawKey: string
  onClose: () => void
  /** Optional extra content rendered below the key (e.g. an activate link) */
  extraContent?: ReactNode
}

export function OneTimeKeyDialog({ open, rawKey, onClose, extraContent }: OneTimeKeyDialogProps) {
  const crud = useCrudToast()
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(rawKey)
      crud.info("Key copied", "Pasted into your clipboard.")
    } catch {
      // fallback: select the input text
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md" data-testid="one-time-key-dialog">
        <DialogHeader>
          <DialogTitle className="font-montserrat">License Key Created</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <p className="text-sm text-muted-foreground">
            Copy this key now. It will <strong>not</strong> be shown again.
          </p>

          <div className="flex items-center gap-2">
            <Input
              data-testid="raw-key-display"
              readOnly
              value={rawKey}
              className="font-mono text-sm"
              onClick={(e) => (e.target as HTMLInputElement).select()}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              data-testid="copy-key-button"
              onClick={handleCopy}
              aria-label="Copy key"
            >
              {copied ? (
                <Check className="w-4 h-4 text-emerald-600" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </Button>
          </div>

          {copied && (
            <p className="text-xs text-emerald-600" data-testid="copy-success">
              Copied to clipboard
            </p>
          )}

          {extraContent}
        </div>

        <DialogFooter>
          <Button onClick={onClose} data-testid="close-key-dialog">
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
