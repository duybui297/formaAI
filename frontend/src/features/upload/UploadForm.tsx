"use client"
import { useState, useCallback, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useToast } from "@/hooks/use-toast"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { LanguageSelect } from "@/components/LanguageSelect"
import { GlossarySelect } from "./GlossarySelect"
import { TrackedChangesModal } from "./TrackedChangesModal"
import { UploadCloud, FileText, Languages, BookA, PlayCircle, ArrowUpRight, Loader2, Coins } from "lucide-react"
import { cn } from "@/lib/utils"
import { detectTrackedChanges } from "@/lib/detectTrackedChanges"
import { chunkedUploadWithProgress, estimateTranslation } from "@/lib/api"
import type { Entitlement, EstimateResponse } from "@/lib/types"

const DEFAULT_MAX_SIZE_BYTES = 25 * 1024 * 1024
// Phase 3: PPTX and native PDF pipelines added. Keep allowlist in sync with backend.
const ALLOWED_EXTS = new Set([".docx", ".pptx", ".pdf", ".xlsx"])

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
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
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

  // US-3.6: Credit estimation — triggered after file + language pair are ready
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null)
  const [estimating, setEstimating] = useState(false)

  const runEstimate = useCallback(async () => {
    if (!file || !targetLang || sourceLang === targetLang) {
      setEstimate(null)
      return
    }
    setEstimating(true)
    try {
      const effectiveScanned = isScannedOverride !== null ? isScannedOverride : isScannedDetected
      const result = await estimateTranslation({
        file,
        source_lang: sourceLang,
        target_lang: targetLang,
        isScannedOverride: effectiveScanned ?? undefined,
      })
      setEstimate(result)
      if (result.is_scanned !== undefined && isScannedDetected === null) {
        setIsScannedDetected(result.is_scanned)
      }
    } catch {
      setEstimate(null)
    } finally {
      setEstimating(false)
    }
  }, [file, targetLang, sourceLang, isScannedOverride, isScannedDetected])

  // Trigger estimate whenever file, languages, or scanned state changes
  useEffect(() => {
    if (!file || !targetLang || sourceLang === targetLang) {
      setEstimate(null)
      return
    }
    runEstimate()
  }, [file, targetLang, sourceLang, isScannedOverride, isScannedDetected, runEstimate])

  const handleFile = useCallback(async (f: File) => {
    const ext = getExt(f.name)
    if (!ALLOWED_EXTS.has(ext)) {
      const msg = "Unsupported file type. Accepted formats: .docx, .pptx, .pdf, .xlsx"
      setError(msg)
      toast({ variant: "destructive", title: "Unsupported file", description: msg })
      return
    }
    if (f.size > maxSizeBytes) {
      const msg = `File too large — your plan allows up to ${formatBytes(maxSizeBytes)}.`
      setError(msg)
      toast({ variant: "destructive", title: "File too large", description: msg })
      return
    }
    setError(null)
    setUploadProgress(null)
    // Reset all tracked-changes state atomically before detection
    setFile(f)
    setTrackedAction(null)
    setHasTrackedChanges(false)
    setShowTrackedModal(false)
    // Phase 4: reset scanned detection state on new file selection
    setIsScannedDetected(null)
    setIsScannedOverride(null)
    setDetecting(true)
    // US-3.6: reset estimate on file change
    setEstimate(null)

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
        toast({ variant: "destructive", title: "Too many files", description: "Upload one file at a time." })
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

  // US-3.6: Insufficient credits blocks submit
  const insufficientCredits = estimate && !estimate.has_sufficient_credits
  const canSubmit = !!file && !!targetLang && sourceLang !== targetLang && !submitting && !detecting && !estimating && !insufficientCredits

  // Chunked upload threshold: files > 10 MB use chunked upload
  const CHUNK_THRESHOLD = 10 * 1024 * 1024

  // Core submit function — called with a resolved action (or null for non-DOCX)
  const submitWithAction = useCallback(
    async (action: "strip" | "preserve" | null) => {
      if (!file || !targetLang) return
      setError(null)
      setSubmitting(true)
      setUploadProgress(null)

      const effectiveScanned = isScannedOverride !== null ? isScannedOverride : isScannedDetected

      try {
        if (file.size > CHUNK_THRESHOLD) {
          // Chunked upload path (AC-4)
          const result = await chunkedUploadWithProgress(file, sourceLang, targetLang, {
            glossaryId: glossaryId || undefined,
            trackedChangesAction: action ?? undefined,
            isScannedOverride: effectiveScanned ?? undefined,
            onProgress: (uploaded, total) => {
              setUploadProgress(Math.round((uploaded / total) * 100))
            },
          })
          setUploadProgress(100)
          setSubmitting(false)
          if (onJobCreated) {
            onJobCreated(result.job_id)
          } else {
            router.push(`/jobs/${result.job_id}`)
          }
          return
        } else {
          // Single-shot upload path (≤ 10 MB)
          const formData = new FormData()
          formData.append("file", file)
          formData.append("source_lang", sourceLang)
          formData.append("target_lang", targetLang)
          if (action) formData.append("tracked_changes_action", action)
          if (glossaryId) formData.append("glossary_id", glossaryId)
          if (effectiveScanned !== null) {
            formData.append("is_scanned_override", String(effectiveScanned))
          }

          const res = await fetch("/api/v1/upload", { method: "POST", body: formData })
          const data = await res.json()

          if (res.ok && data.is_scanned !== undefined) {
            setIsScannedDetected(data.is_scanned as boolean)
          }

          if (!res.ok) {
            let msg: string
            const detail = data.detail
            const is413 = res.status === 413
            if (typeof detail === "object" && detail !== null) {
              const errCode = (detail as Record<string, unknown>).error as string | undefined
              if (errCode === "LICENSE_REQUIRED") {
                msg = ((detail as Record<string, unknown>).message as string) ?? "A valid license is required."
              } else if (errCode === "QUOTA_EXCEEDED") {
                msg = ((detail as Record<string, unknown>).message as string) ?? "Monthly quota exceeded."
              } else if (errCode === "FEATURE_NOT_IN_PLAN") {
                const feature = (detail as Record<string, unknown>).feature as string | undefined
                const featureName = feature === "ocr" ? "OCR" : feature === "glossary" ? "Glossary" : feature ?? "This feature"
                msg = ((detail as Record<string, unknown>).message as string) ?? `${featureName} is not available.`
              } else {
                msg = ((detail as Record<string, unknown>).message as string) ?? "Upload failed."
              }
            } else if (typeof detail === "string") {
              msg = detail
            } else {
              msg = (data as Record<string, unknown>).error as string ?? "Upload failed."
            }
            if (is413) {
              msg = `File too large — your plan allows up to ${formatBytes(maxSizeBytes)}.`
            }
            setError(msg)
            toast({ variant: "destructive", title: "Upload failed", description: msg })
            setSubmitting(false)
            return
          }

          if (onJobCreated) {
            onJobCreated((data as { job_id: string }).job_id)
          } else {
            router.push(`/jobs/${(data as { job_id: string }).job_id}`)
          }
          toast({ variant: "success", title: "Translation started", description: file.name })
          return
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed."
        setError(msg)
        toast({ variant: "destructive", title: "Upload failed", description: msg })
        setSubmitting(false)
      }
    },
    [file, targetLang, sourceLang, glossaryId, isScannedOverride, isScannedDetected, router, toast, onJobCreated, maxSizeBytes]
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
                dragState === "valid" ? "border-primary bg-primary/5" :
                dragState === "multi" ? "border-red-400 bg-red-50" :
                "border-input bg-muted hover:border-input hover:bg-muted/50"
              )}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={() => setDragState("idle")}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              {file ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-16 h-16 bg-card rounded-xl shadow-sm border border-border flex items-center justify-center">
                    <FileText className="w-8 h-8 text-primary" />
                  </div>
                  <div>
                    <p className="text-foreground font-medium">{file.name}</p>
                    <p className="text-muted-foreground text-sm">{formatBytes(file.size)}</p>
                  </div>
                  <button
                    type="button"
                    className="text-sm text-primary hover:text-primary font-medium underline mt-2 relative z-20"
                    onClick={(e) => { e.stopPropagation(); setFile(null) }}
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 bg-card rounded-full shadow-sm border border-border flex items-center justify-center">
                    <UploadCloud className="w-8 h-8 text-primary" />
                  </div>
                  <div>
                    <p className="text-lg font-medium text-foreground">
                      {dragState === "valid" ? "Release to upload" :
                       dragState === "multi" ? "One file at a time only" :
                       "Drag & drop your file here"}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Supports DOCX, PDF, PPTX, XLSX up to {formatBytes(maxSizeBytes)}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 mt-2 w-64">
                    <div className="h-px bg-input flex-1" />
                    <span className="text-xs text-muted-foreground uppercase font-medium">or</span>
                    <div className="h-px bg-input flex-1" />
                  </div>
                  <span className="bg-card border border-border shadow-sm text-sm font-medium px-4 py-2 rounded-lg text-foreground">
                    Browse Files
                  </span>
                </div>
              )}
            </div>

            {/* Phase 4: Scanned PDF detection */}
            {file && getExt(file.name) === ".pdf" && isScannedDetected !== null && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <span>
                  {isScannedOverride !== null
                    ? `Changed to: ${isScannedOverride ? "scanned" : "native"} PDF`
                    : `Detected: ${isScannedDetected ? "scanned" : "native"} PDF`}
                </span>
                <button
                  type="button"
                  className="text-xs text-primary underline hover:text-primary ml-1"
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
                className="bg-primary/10 dark:bg-primary/15 border border-primary/20 dark:border-primary/25 rounded-xl px-4 py-3 text-sm space-y-1"
                data-testid="entitlement-info"
              >
                <p className="text-primary font-medium">
                  {entitlement.tier ?? "Active"} plan
                </p>
                <p className="text-primary/80" data-testid="max-file-size">
                  Max file size: {formatBytes(maxSizeBytes)}
                </p>
                {entitlement.monthly_quota != null ? (
                  <p className="text-primary/80" data-testid="quota-remaining">
                    {entitlement.monthly_quota - entitlement.quota_used} / {entitlement.monthly_quota} documents left this month
                  </p>
                ) : (
                  <p className="text-primary/80" data-testid="quota-remaining">
                    Unlimited documents
                  </p>
                )}
              </div>
            )}

            {/* US-3.6: Credit estimate card */}
            {estimating && file && targetLang && (
              <div className="rounded-xl px-4 py-3 text-sm flex items-center gap-2 bg-muted border border-border">
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                <span className="text-muted-foreground">Estimating cost...</span>
              </div>
            )}
            {estimate && !estimating && (
              <div
                className={cn(
                  "rounded-xl px-4 py-3 text-sm space-y-1",
                  estimate.has_sufficient_credits
                    ? "bg-muted border border-border"
                    : "bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800"
                )}
                data-testid="credit-estimate"
              >
                <div className="flex items-center gap-2 text-foreground">
                  <Coins className="w-4 h-4 text-muted-foreground" />
                  <span className="font-medium">
                    {estimate.word_count.toLocaleString()} words
                  </span>
                  <span className="text-muted-foreground">·</span>
                  <span className="font-semibold">
                    {estimate.credit_cost.toLocaleString()} credits
                  </span>
                  {estimate.is_scanned && (
                    <Badge variant="outline" className="text-xs ml-1">OCR</Badge>
                  )}
                </div>
                {!estimate.has_sufficient_credits && (
                  <p className="text-red-600 dark:text-red-400 text-xs">
                    Insufficient quota.{" "}
                    <button
                      type="button"
                      className="underline hover:text-red-700"
                      onClick={() => router.push("/pricing")}
                    >
                      Top up
                    </button>{" "}
                    to continue.
                  </p>
                )}
              </div>
            )}

            {/* Language Pair */}
            <div className="bg-card p-6 rounded-xl border border-border shadow-md space-y-5">
              <h3 className="font-semibold text-foreground flex items-center gap-2 mb-2">
                <Languages className="w-4 h-4 text-muted-foreground" />
                Language Pair
              </h3>
              <div className="space-y-4">
                <LanguageSelect
                  label="Source"
                  value={sourceLang}
                  onValueChange={(v) => { setSourceLang(v); setEstimate(null) }}
                  includeAutoDetect
                  placeholder="Auto-detect (Recommended)"
                />
                <LanguageSelect
                  label="Target"
                  value={targetLang}
                  onValueChange={(v) => { setTargetLang(v); setEstimate(null) }}
                  placeholder="Select target language"
                />
                {targetLang && sourceLang !== "auto" && sourceLang === targetLang && (
                  <p className="text-sm text-red-600">
                    Source and target language must be different.
                  </p>
                )}
              </div>
            </div>

            {/* Glossary — hidden when glossary_allowed === false */}
            {glossaryAllowed ? (
              <div className="bg-card p-6 rounded-xl border border-border shadow-md space-y-4">
                <h3 className="font-semibold text-foreground flex items-center gap-2">
                  <BookA className="w-4 h-4 text-muted-foreground" />
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
                className="bg-card p-6 rounded-xl border border-border shadow-md space-y-4 opacity-60"
                data-testid="glossary-disabled"
              >
                <h3 className="font-semibold text-muted-foreground flex items-center gap-2">
                  <BookA className="w-4 h-4 text-muted-foreground" />
                  Glossary
                  <span className="ml-auto text-xs font-normal text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                    Pro feature
                  </span>
                </h3>
                <p className="text-xs text-muted-foreground">Upgrade to Pro to use custom glossaries.</p>
              </div>
            )}

            {/* Start Translation Button */}
            <button
              type="submit"
              disabled={!canSubmit}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-semibold shadow-sm transition-all relative overflow-hidden",
                !canSubmit
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {uploadProgress !== null && submitting && (
                <div
                  className="absolute inset-y-0 left-0 bg-primary/80 transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2">
                <PlayCircle className="w-5 h-5" />
                {submitting
                  ? uploadProgress !== null
                    ? `Uploading ${uploadProgress}%`
                    : "Uploading..."
                  : "Start Translation"}
              </span>
            </button>
            {error && (
              <Alert variant="destructive" className="mt-3">
                <AlertDescription className="flex items-start justify-between gap-3">
                  <span className="text-sm">{error}</span>
                  {error.includes("too large") && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700 whitespace-nowrap"
                      onClick={() => router.push("/pricing")}
                    >
                      Upgrade for larger files
                      <ArrowUpRight className="w-3 h-3" />
                    </Button>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </div>
        </div>

        <input
          id="file-input"
          type="file"
          accept=".docx,.pptx,.pdf,.xlsx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
