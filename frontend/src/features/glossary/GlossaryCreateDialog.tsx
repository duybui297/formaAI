"use client"
import { useState } from "react"
import { useCrudToast } from "@/hooks/use-crud-toast"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { LanguageSelect } from "@/components/LanguageSelect"
import { authFetch } from "@/lib/auth"

interface GlossaryCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void  // no argument — dialog closes internally; parent invalidates cache
}

export function GlossaryCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: GlossaryCreateDialogProps) {
  const crud = useCrudToast()
  const [name, setName] = useState("")
  const [sourceLang, setSourceLang] = useState("")
  const [targetLang, setTargetLang] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const canSubmit = name.trim().length > 0 && !!sourceLang && !!targetLang && !submitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    try {
      const res = await authFetch("/v1/glossaries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), source_lang: sourceLang, target_lang: targetLang }),
        throwOnError: false,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const msg = data.detail || data.error || "Failed to create glossary."
        crud.failed("create", "glossary", msg)
        return
      }
      // Reset form state
      setName("")
      setSourceLang("")
      setTargetLang("")
      crud.created("Glossary", name.trim())
      onCreated()
    } catch (err) {
      crud.failed("create", "glossary", err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-[--font-montserrat]">Create Glossary</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1">
            <label className="text-sm text-foreground">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Medical Terms EN→VI"
              maxLength={100}
              required
            />
          </div>
          <LanguageSelect
            label="Source Language"
            value={sourceLang}
            onValueChange={setSourceLang}
            placeholder="Select source language"
          />
          <LanguageSelect
            label="Target Language"
            value={targetLang}
            onValueChange={setTargetLang}
            placeholder="Select target language"
          />
          <DialogFooter className="mt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-violet-500 hover:bg-violet-600 text-white"
            >
              {submitting ? "Creating…" : "Create Glossary"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
