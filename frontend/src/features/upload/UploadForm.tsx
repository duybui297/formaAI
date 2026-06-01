"use client"
import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { LanguageSelect } from "@/components/LanguageSelect"
import { GlossarySelect } from "./GlossarySelect"
import { TrackedChangesModal } from "./TrackedChangesModal"
import { UploadCloud, FileText, Languages, BookA, PlayCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { detectTrackedChanges } from "@/lib/detectTrackedChanges"
import type { Entitlement } from "@/lib/types"

const DEFAULT_MAX_SIZE_BYTES = 25 * 1024 * 1024
// Phase 3: PPTX and native PDF pipelines added. Keep allowlist in sync with backend.
const ALLOWED_EXTS = new Set([".docx", ".pptx", ".pdf"])

function getExt(filename: string): string {
  return filename.slice(filename.lastIndexOf(".")).toLowerCase()
}

function formatBytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

interface UploadFormProps {
  onJobCreated?: (jobId: string) => void
  entitlement?: Entitlement | null
}

export function UploadForm({ onJobCreated, entitlement }: UploadFormProps = {}) {
  const maxSizeBytes = entitlement?.max_file_bytes ?? DEFAULT_MAX_SIZE_BYTES
  const ocrAllowed = entitlement == null || entitlement.ocr_allowed !== false
  const glossaryAllowed = entitlement == null || entitlement.glossary_allowed !== false
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
    if (f.size > maxSizeBytes) {
      const msg = `File too large — your plan allows up to ${formatBytes(maxSizeBytes)}.`
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
  }, [toast, maxSizeBytes])

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
          // Handle structured license error bodies from backend
          let msg: string
          const detail = data.detail
          if (typeof detail === "object" && detail !== null) {
            const errCode = detail.error as string | undefined
            if (errCode === "LICENSE_REQUIRED") {
              msg = detail.message ?? "A valid license is required to translate documents."
            } else if (errCode === "QUOTA_EXCEEDED") {
              msg = detail.message ?? "Monthly translation quota exceeded. Upgrade your plan."
            } else if (errCode === "FEATURE_NOT_IN_PLAN") {
              const feature = detail.feature as string | undefined
              const featureName = feature === "ocr" ? "OCR" : feature === "glossary" ? "Glossary" : feature ?? "This feature"
              msg = detail.message ?? `${featureName} is not available on your current plan.`
            } else {
              msg = detail.message ?? "Upload failed. Please try again."
            }
          } else if (typeof detail === "string") {
            msg = detail
          } else {
            msg = data.error ?? "Upload failed. Please try again."
          }
          setError(msg)
          toast({
            variant: "destructive",
            description: msg,
          })
          setSubmitting(false)
          return
        }
        if (onJobCreated) {
          onJobCreated(data.job_id)
        } else {
          router.push(`/jobs/${data.job_id}`)
        }
      } catch {
        toast({
          variant: "destructive",
          description: "Upload failed. Please check your connection.",
        })
        setSubmitting(false)
      }
    },
    [file, targetLang, sourceLang, glossaryId, isScannedOverride, isScannedDetected, router, toast, onJobCreated]
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

  return (
    <>
      <form onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Left 3/5 — Upload Area */}
          <div className="lg:col-span-3 space-y-6">
            <div
              className={cn(
                "border-2 border-dashed rounded-2xl p-16 text-center transition-all relative overflow-hidden cursor-pointer min-h-[320px] flex items-center justify-center",
                dragState === "valid" ? "border-indigo-500 bg-indigo-50/50" :
                dragState === "multi" ? "border-red-400 bg-red-50" :
                "border-zinc-300 bg-zinc-50 hover:border-zinc-400 hover:bg-zinc-100/50"
              )}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={() => setDragState("idle")}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              {file ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-16 h-16 bg-white rounded-xl shadow-sm border border-zinc-200 flex items-center justify-center">
                    <FileText className="w-8 h-8 text-indigo-600" />
                  </div>
                  <div>
                    <p className="text-zinc-900 font-medium">{file.name}</p>
                    <p className="text-zinc-500 text-sm">{formatBytes(file.size)}</p>
                  </div>
                  <button
                    type="button"
                    className="text-sm text-indigo-600 hover:text-indigo-700 font-medium underline mt-2 relative z-20"
                    onClick={(e) => { e.stopPropagation(); setFile(null) }}
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 bg-white rounded-full shadow-sm border border-zinc-200 flex items-center justify-center">
                    <UploadCloud className="w-8 h-8 text-indigo-600" />
                  </div>
                  <div>
                    <p className="text-lg font-medium text-zinc-900">
                      {dragState === "valid" ? "Release to upload" :
                       dragState === "multi" ? "One file at a time only" :
                       "Drag & drop your file here"}
                    </p>
                    <p className="text-sm text-zinc-500 mt-1">
                      Supports DOCX, PDF, PPTX up to {formatBytes(maxSizeBytes)}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 mt-2 w-64">
                    <div className="h-px bg-zinc-300 flex-1" />
                    <span className="text-xs text-zinc-400 uppercase font-medium">or</span>
                    <div className="h-px bg-zinc-300 flex-1" />
                  </div>
                  <span className="bg-white border border-zinc-200 shadow-sm text-sm font-medium px-4 py-2 rounded-lg text-zinc-700">
                    Browse Files
                  </span>
                </div>
              )}
            </div>

            {/* Phase 4: Scanned PDF detection */}
            {file && getExt(file.name) === ".pdf" && isScannedDetected !== null && (
              <div className="flex items-center gap-1 text-xs text-zinc-600">
                <span>
                  {isScannedOverride !== null
                    ? `Changed to: ${isScannedOverride ? "scanned" : "native"} PDF`
                    : `Detected: ${isScannedDetected ? "scanned" : "native"} PDF`}
                </span>
                <button
                  type="button"
                  className="text-xs text-indigo-600 underline hover:text-indigo-800 ml-1"
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
          </div>

          {/* Right 2/5 — Settings Sidebar */}
          <div className="lg:col-span-2 space-y-6">
            {/* Entitlement info — quota + file size limits */}
            {entitlement?.has_active && (
              <div
                className="bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3 text-sm space-y-1"
                data-testid="entitlement-info"
              >
                <p className="text-indigo-800 font-medium">
                  {entitlement.tier ?? "Active"} plan
                </p>
                <p className="text-indigo-700" data-testid="max-file-size">
                  Max file size: {formatBytes(maxSizeBytes)}
                </p>
                {entitlement.monthly_quota != null ? (
                  <p className="text-indigo-700" data-testid="quota-remaining">
                    {entitlement.monthly_quota - entitlement.quota_used} / {entitlement.monthly_quota} documents left this month
                  </p>
                ) : (
                  <p className="text-indigo-700" data-testid="quota-remaining">
                    Unlimited documents
                  </p>
                )}
              </div>
            )}

            {/* Language Pair */}
            <div className="bg-white p-6 rounded-xl border border-zinc-200 shadow-md space-y-5">
              <h3 className="font-semibold text-zinc-900 flex items-center gap-2 mb-2">
                <Languages className="w-4 h-4 text-indigo-500" />
                Language Pair
              </h3>
              <div className="space-y-4">
                <LanguageSelect
                  label="Source"
                  value={sourceLang}
                  onValueChange={setSourceLang}
                  includeAutoDetect
                  placeholder="Auto-detect (Recommended)"
                />
                <LanguageSelect
                  label="Target"
                  value={targetLang}
                  onValueChange={setTargetLang}
                  placeholder="Select target language"
                />
              </div>
            </div>

            {/* Glossary — hidden when glossary_allowed === false */}
            {glossaryAllowed ? (
              <div className="bg-white p-6 rounded-xl border border-zinc-200 shadow-md space-y-4">
                <h3 className="font-semibold text-zinc-900 flex items-center gap-2">
                  <BookA className="w-4 h-4 text-indigo-500" />
                  Glossary
                </h3>
                <GlossarySelect
                  sourceLang={sourceLang === "auto" ? "" : sourceLang}
                  targetLang={targetLang}
                  value={glossaryId}
                  onChange={setGlossaryId}
                />
              </div>
            ) : (
              <div
                className="bg-white p-6 rounded-xl border border-zinc-200 shadow-md space-y-4 opacity-60"
                data-testid="glossary-disabled"
              >
                <h3 className="font-semibold text-zinc-500 flex items-center gap-2">
                  <BookA className="w-4 h-4 text-zinc-400" />
                  Glossary
                  <span className="ml-auto text-xs font-normal text-zinc-400 bg-zinc-100 px-2 py-0.5 rounded-full">
                    Pro feature
                  </span>
                </h3>
                <p className="text-xs text-zinc-400">Upgrade to Pro to use custom glossaries.</p>
              </div>
            )}

            {/* Start Translation Button */}
            <button
              type="submit"
              disabled={!canSubmit}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold shadow-sm transition-all",
                !canSubmit
                  ? "bg-zinc-100 text-zinc-400 cursor-not-allowed"
                  : "bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-md hover:-translate-y-0.5"
              )}
            >
              <PlayCircle className="w-5 h-5" />
              {submitting ? "Uploading..." : "Start Translation"}
            </button>
            {error && (
              <p role="alert" className="text-sm text-red-600 mt-1">{error}</p>
            )}
          </div>
        </div>

        <input
          id="file-input"
          type="file"
          accept=".docx,.pptx,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/pdf"
          className="hidden"
          onChange={e => {
            const f = e.target.files?.[0]
            if (f) handleFile(f)
            e.target.value = ""
          }}
        />
      </form>

      <TrackedChangesModal
        open={showTrackedModal}
        onOpenChange={open => {
          if (!open) {
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
