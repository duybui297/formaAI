"use client"
import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { LanguageSelect } from "./LanguageSelect"
import { GlossarySelect } from "./GlossarySelect"
import { TrackedChangesModal } from "./TrackedChangesModal"
import { CloudUpload } from "lucide-react"
import { detectTrackedChanges } from "@/lib/detectTrackedChanges"

const MAX_SIZE_BYTES = 25 * 1024 * 1024
// Phase 3: PPTX and native PDF pipelines added. Keep allowlist in sync with backend.
const ALLOWED_EXTS = new Set([".docx", ".pptx", ".pdf"])

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
  const [glossaryId, setGlossaryId] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // B4 Option A: client-side tracked-changes state
  // hasTrackedChanges: set by detectTrackedChanges() on file selection
  // trackedAction: null means user hasn't chosen yet; guard is live when null
  const [hasTrackedChanges, setHasTrackedChanges] = useState(false)
  const [showTrackedModal, setShowTrackedModal] = useState(false)
  // trackedAction: null = not yet decided; "strip"/"preserve" = decided by modal
  const [trackedAction, setTrackedAction] = useState<"strip" | "preserve" | null>(null)
  // detecting: true while detectTrackedChanges() is in flight — blocks Submit
  const [detecting, setDetecting] = useState(false)

  // Phase 4: D-04-17 — Scanned PDF detection + user override
  // isScannedDetected: null = not yet detected / not a PDF; true/false = detection result
  // isScannedOverride: null = use auto; true/false = user override
  const [isScannedDetected, setIsScannedDetected] = useState<boolean | null>(null)
  const [isScannedOverride, setIsScannedOverride] = useState<boolean | null>(null)

  const handleFile = useCallback(async (f: File) => {
    const ext = getExt(f.name)
    if (!ALLOWED_EXTS.has(ext)) {
      const msg = "Unsupported file type. Accepted formats: .docx, .pptx, .pdf"
      setError(msg)
      toast({ variant: "destructive", description: msg })
      return
    }
    if (f.size > MAX_SIZE_BYTES) {
      const msg = "File too large — maximum is 25 MB."
      setError(msg)
      toast({ variant: "destructive", description: msg })
      return
    }
    setError(null)
    // Reset all tracked-changes state atomically before detection
    setFile(f)
    setTrackedAction(null)
    setHasTrackedChanges(false)
    setShowTrackedModal(false)
    // Phase 4: reset scanned detection state on new file selection
    setIsScannedDetected(null)
    setIsScannedOverride(null)
    setDetecting(true)

    // B4 Option A: detect tracked changes before any upload (DOCX only — PPTX/PDF have no TC)
    const hasTC = ext === ".docx" ? await detectTrackedChanges(f) : false
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
      setError(null)
      setSubmitting(true)
      try {
        const formData = new FormData()
        formData.append("file", file)
        formData.append("source_lang", sourceLang)
        formData.append("target_lang", targetLang)
        if (action) {
          formData.append("tracked_changes_action", action)
        }
        if (glossaryId) {
          formData.append("glossary_id", glossaryId)
        }
        // Phase 4: D-04-17 — send is_scanned_override only when user explicitly overrode
        const effectiveScanned = isScannedOverride !== null ? isScannedOverride : isScannedDetected
        if (effectiveScanned !== null) {
          formData.append("is_scanned_override", String(effectiveScanned))
        }

        const res = await fetch("/api/upload", { method: "POST", body: formData })
        const data = await res.json()

        // Phase 4: D-04-17 — capture scanned detection result from upload response
        if (res.ok && data.is_scanned !== undefined) {
          setIsScannedDetected(data.is_scanned as boolean)
        }

        if (!res.ok) {
          const msg = data.detail || data.error || "Upload failed. Please try again."
          setError(msg)
          toast({
            variant: "destructive",
            description: msg,
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
    [file, targetLang, sourceLang, glossaryId, router, toast]
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
      : "Drop your document here — DOCX, PPTX, or native PDF"

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
        {/* Phase 4: D-04-17 — Scanned PDF detection result + override toggle */}
        {file && getExt(file.name) === ".pdf" && isScannedDetected !== null && (
          <div className="flex items-center gap-1 mt-2 text-xs text-slate-600">
            <span>
              {isScannedOverride !== null
                ? `Changed to: ${isScannedOverride ? "scanned" : "native"} PDF`
                : `Detected: ${isScannedDetected ? "scanned" : "native"} PDF`}
            </span>
            <button
              type="button"
              className="text-xs text-violet-600 underline hover:text-violet-800 ml-1"
              onClick={() =>
                setIsScannedOverride((v) =>
                  v === null ? !isScannedDetected : null
                )
              }
            >
              {isScannedOverride !== null ? "Reset to auto" : "Change"}
            </button>
          </div>
        )}

        <input
          id="file-input"
          type="file"
          accept=".docx,.pptx,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/pdf"
          className="hidden"
          onChange={e => {
            const f = e.target.files?.[0]
            if (f) handleFile(f)
            // Clear the input value so selecting the SAME file again fires
            // onChange. Without this, the browser skips onChange when the
            // selected filename matches the previous selection — breaks the
            // "Escape modal → reselect same file" flow.
            e.target.value = ""
          }}
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

        {/* Glossary picker */}
        <GlossarySelect
          sourceLang={sourceLang === "auto" ? "" : sourceLang}
          targetLang={targetLang}
          value={glossaryId}
          onChange={setGlossaryId}
        />

        {/* Submit */}
        <Button
          type="submit"
          disabled={!canSubmit}
          className="w-full bg-indigo-600 hover:bg-indigo-700 min-h-[48px]"
        >
          {submitting ? "Uploading..." : "Translate Document"}
        </Button>
        {error && (
          <p role="alert" className="text-sm text-red-600 mt-1">
            {error}
          </p>
        )}
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
