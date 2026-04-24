"use client"
import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { LanguageSelect } from "./LanguageSelect"
import { TrackedChangesModal } from "./TrackedChangesModal"
import { CloudUpload } from "lucide-react"
import { detectTrackedChanges } from "@/lib/detectTrackedChanges"

const MAX_SIZE_BYTES = 25 * 1024 * 1024
const ALLOWED_EXTS = new Set([".docx", ".pdf", ".pptx"])

function getExt(filename: string): string {
  return filename.slice(filename.lastIndexOf(".")).toLowerCase()
}

function formatBytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function UploadForm() {
  const router = useRouter()
  const { toast } = useToast()

  const [file, setFile] = useState<File | null>(null)
  const [dragState, setDragState] = useState<"idle" | "valid" | "multi">("idle")
  const [sourceLang, setSourceLang] = useState("auto")
  const [targetLang, setTargetLang] = useState("")
  const [submitting, setSubmitting] = useState(false)

  // B4 Option A: client-side tracked-changes state
  // hasTrackedChanges: set by detectTrackedChanges() on file selection
  // trackedAction: null means user hasn't chosen yet; guard is live when null
  const [hasTrackedChanges, setHasTrackedChanges] = useState(false)
  const [showTrackedModal, setShowTrackedModal] = useState(false)
  // trackedAction: null = not yet decided; "strip"/"preserve" = decided by modal
  const [trackedAction, setTrackedAction] = useState<"strip" | "preserve" | null>(null)
  // detecting: true while detectTrackedChanges() is in flight — blocks Submit
  const [detecting, setDetecting] = useState(false)

  const handleFile = useCallback(async (f: File) => {
    const ext = getExt(f.name)
    if (!ALLOWED_EXTS.has(ext)) {
      toast({
        variant: "destructive",
        description: "Unsupported file type. Upload a DOCX, PDF, or PPTX.",
      })
      return
    }
    if (f.size > MAX_SIZE_BYTES) {
      toast({
        variant: "destructive",
        description: "File too large — maximum is 25 MB.",
      })
      return
    }
    // Reset all tracked-changes state atomically before detection
    setFile(f)
    setTrackedAction(null)
    setHasTrackedChanges(false)
    setShowTrackedModal(false)
    setDetecting(true)

    // B4 Option A: detect tracked changes before any upload
    const hasTC = await detectTrackedChanges(f)
    setHasTrackedChanges(hasTC)
    setDetecting(false)
  }, [toast])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragState("idle")
      const files = Array.from(e.dataTransfer.files)
      if (files.length > 1) {
        toast({ variant: "destructive", description: "Upload one file at a time." })
        return
      }
      if (files[0]) handleFile(files[0])
    },
    [handleFile, toast]
  )

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragState(e.dataTransfer.items.length > 1 ? "multi" : "valid")
  }

  const canSubmit = !!file && !!targetLang && !submitting && !detecting

  // Core submit function — called with a resolved action (or null for non-DOCX)
  const submitWithAction = useCallback(
    async (action: "strip" | "preserve" | null) => {
      if (!file || !targetLang) return
      setSubmitting(true)
      try {
        const formData = new FormData()
        formData.append("file", file)
        formData.append("source_lang", sourceLang)
        formData.append("target_lang", targetLang)
        if (action) {
          formData.append("tracked_changes_action", action)
        }

        const res = await fetch("/api/upload", { method: "POST", body: formData })
        const data = await res.json()

        if (!res.ok) {
          toast({
            variant: "destructive",
            description: data.detail || data.error || "Upload failed.",
          })
          setSubmitting(false)
          return
        }
        router.push(`/jobs/${data.job_id}`)
      } catch {
        toast({
          variant: "destructive",
          description: "Upload failed. Please check your connection.",
        })
        setSubmitting(false)
      }
    },
    [file, targetLang, sourceLang, router, toast]
  )

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !targetLang) return

    // B4 Option A: if tracked changes present and user hasn't decided yet → show modal
    if (hasTrackedChanges && trackedAction === null) {
      setShowTrackedModal(true)
      return // Do NOT submit yet
    }

    await submitWithAction(trackedAction)
  }

  const dropZoneClass =
    dragState === "valid"
      ? "border-indigo-500 bg-indigo-50"
      : dragState === "multi"
      ? "border-red-400 bg-red-50"
      : "border-slate-300 bg-white"

  const dropZoneText =
    dragState === "valid"
      ? "Release to upload"
      : dragState === "multi"
      ? "One file at a time only"
      : "Drop your DOCX, PDF, or PPTX here"

  return (
    <>
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* Drop zone */}
        <div
          className={`flex flex-col items-center justify-center min-h-[200px] border-2 border-dashed rounded-lg cursor-pointer transition-colors ${dropZoneClass}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={() => setDragState("idle")}
          onClick={() => document.getElementById("file-input")?.click()}
        >
          {file ? (
            <div className="flex items-center gap-2 text-sm text-slate-700">
              <Badge variant="outline">
                {getExt(file.name).toUpperCase().slice(1)}
              </Badge>
              <span>{file.name}</span>
              <span className="text-xs text-slate-500">{formatBytes(file.size)}</span>
            </div>
          ) : (
            <>
              <CloudUpload className="h-10 w-10 text-slate-400 mb-2" />
              <p className="text-sm text-slate-700">{dropZoneText}</p>
              <p className="text-xs text-slate-500 mt-1">
                or click to choose a file &middot; max 25 MB
              </p>
            </>
          )}
        </div>
        <input
          id="file-input"
          type="file"
          accept=".docx,.pdf,.pptx"
          className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
        />

        {/* Language row */}
        <div className="flex items-end gap-4">
          <div className="flex-1">
            <LanguageSelect
              label="Source Language"
              value={sourceLang}
              onValueChange={setSourceLang}
              includeAutoDetect
              placeholder="Auto-detect"
            />
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="min-h-[48px] min-w-[48px]"
            disabled={sourceLang === "auto"}
            title="Swap languages"
            aria-label="Swap source and target languages"
            onClick={() => {
              if (sourceLang !== "auto") {
                const tmp = sourceLang
                setSourceLang(targetLang)
                setTargetLang(tmp)
              }
            }}
          >
            &#8596;
          </Button>
          <div className="flex-1">
            <LanguageSelect
              label="Target Language"
              value={targetLang}
              onValueChange={setTargetLang}
              placeholder="Select target language"
            />
          </div>
        </div>

        {/* Submit */}
        <Button
          type="submit"
          disabled={!canSubmit}
          className="w-full bg-indigo-600 hover:bg-indigo-700 min-h-[48px]"
        >
          {submitting ? "Uploading..." : "Translate Document"}
        </Button>
      </form>

      {/* Tracked-changes modal (D-13) — shown BEFORE submit (B4 Option A) */}
      <TrackedChangesModal
        open={showTrackedModal}
        onOpenChange={open => {
          if (!open) {
            // Dialog dismissed via Escape/overlay → treat as cancel
            setFile(null)
            setTrackedAction(null)
            setHasTrackedChanges(false)
            setShowTrackedModal(false)
          }
        }}
        onApply={action => {
          setShowTrackedModal(false)
          setTrackedAction(action)
          submitWithAction(action)
        }}
        onCancel={() => {
          setFile(null)
          setTrackedAction(null)
          setHasTrackedChanges(false)
          setShowTrackedModal(false)
        }}
      />
    </>
  )
}
