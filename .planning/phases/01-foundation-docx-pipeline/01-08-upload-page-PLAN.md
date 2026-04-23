---
phase: 01-foundation-docx-pipeline
plan: "08"
type: execute
wave: 4
depends_on:
  - "07"
files_modified:
  - frontend/src/app/upload/page.tsx
  - frontend/src/app/api/upload/route.ts
  - frontend/src/components/UploadForm.tsx
  - frontend/src/components/LanguageSelect.tsx
  - frontend/src/components/NavBar.tsx
  - frontend/src/lib/detectTrackedChanges.ts
autonomous: true
requirements:
  - UPLD-01
  - UPLD-02
  - UPLD-03
  - UPLD-04
  - UPLD-05
  - LANG-01
  - LANG-02

# NOTE — UPLD-04 glossary picker UI: deferred to Phase 2 per D-15.
# terminology plumbing covered by Plan 03 (INFRA-02 coverage).

must_haves:
  truths:
    - "Drop zone shows dashed border at rest, indigo border + bg on drag-hover, handles one file at a time"
    - "File rejected with toast if >25MB or unsupported format"
    - "LanguageSelect uses language code as form value and display name as label text"
    - "LanguageSelect shows auto-detect as first source option, VN/EN/JA/ZH in Recommended group"
    - "Submit button is disabled until file selected AND target language selected"
    - "Client reads DOCX bytes with jszip before first POST to detect tracked changes (Option A)"
    - "If tracked changes detected, modal shown BEFORE form submit — user picks before any upload"
    - "Modal cancel resets file and closes without upload"
    - "Modal Apply Selection sets tracked_changes_action then submits FormData with all fields"
    - "Form submit posts to /api/upload (Next.js route handler) → redirects to /jobs/[id]"
  artifacts:
    - path: "frontend/src/lib/detectTrackedChanges.ts"
      provides: "Client-side DOCX tracked-changes detector using jszip (Option A per B4)"
      exports: ["detectTrackedChanges"]
    - path: "frontend/src/app/upload/page.tsx"
      provides: "Upload page with UploadForm component"
    - path: "frontend/src/app/api/upload/route.ts"
      provides: "Next.js proxy route: forwards FormData to FastAPI POST /upload"
    - path: "frontend/src/components/UploadForm.tsx"
      provides: "Drop zone + LanguageSelect + tracked-changes modal + submit"
    - path: "frontend/src/components/LanguageSelect.tsx"
      provides: "Source/target shadcn Select with Recommended group; uses code as value"
  key_links:
    - from: "frontend/src/components/UploadForm.tsx file selection"
      to: "frontend/src/lib/detectTrackedChanges.ts"
      via: "detectTrackedChanges(file) called on file selection — modal before first POST"
    - from: "frontend/src/components/UploadForm.tsx"
      to: "frontend/src/app/api/upload/route.ts"
      via: "fetch POST /api/upload with FormData including tracked_changes_action"
    - from: "frontend/src/app/api/upload/route.ts"
      to: "FastAPI POST /upload"
      via: "fetch(backendUrl + '/upload', {body: backendForm})"
---

<objective>
Build the upload page: drag-and-drop zone, source/target language selectors (code-based values),
client-side tracked-changes detection (Option A: jszip + XML check BEFORE submit), modal for user choice,
and the Next.js proxy route handler.

B4 design choice — Option A (client-side detection):
  - On file selection, client reads DOCX bytes with jszip and checks word/document.xml for <w:ins> / <w:del>.
  - If found, modal shown BEFORE first POST. Once user picks strip/preserve/cancel, FormData is built
    with tracked_changes_action appended and single POST fires.
  - No two-phase upload, no dry_run endpoint needed. Self-contained in frontend.
  - jszip added to frontend/package.json (already in Next.js ecosystem via docx-preview patterns).

B5 note: LanguageSelect uses language code as the form value (e.g. "vi", "en") and displays name.
The /api/upload route.ts forwards source_lang/target_lang as codes to FastAPI.

Purpose: The primary user-facing entry point.
Output: /upload route fully functional; tracked-changes flow works before upload occurs.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md

<interfaces>
<!-- Drop zone states (UI-SPEC Interaction Contracts) -->
<!--   Idle: dashed border-slate-300, cloud-upload icon, "Drop your DOCX, PDF, or PPTX here" -->
<!--   Drag-hover (valid single file): border-indigo-500, bg-indigo-50, "Release to upload" -->
<!--   Drag-hover (multi-file): border-red-400, bg-red-50, "One file at a time only" -->
<!--   File selected: filename chip + format badge + size text, drop zone collapses to 40px -->
<!--   Rejected-format: Toast "Unsupported file type. Upload a DOCX, PDF, or PPTX." -->
<!--   Rejected-too-large: Toast "File too large — maximum is 25 MB." -->
<!--   Rejected-multi: Toast "Upload one file at a time." -->

<!-- Tracked-changes modal (D-13 / UI-SPEC) — shown BEFORE submit (Option A) -->
<!--   Title: "Tracked Changes Detected" -->
<!--   Body: "This document has unresolved tracked changes. How would you like to handle them?" -->
<!--   RadioGroup options: strip / preserve / cancel -->
<!--   Confirm CTA: "Apply Selection" -->
<!--   Cancel: "Cancel Upload" → resets file, closes dialog -->

<!-- Language selectors (UI-SPEC) — B5: code as value, name as display -->
<!--   Source: default "auto"; placeholder "Auto-detect" -->
<!--   Target: no default, required; placeholder "Select target language" -->
<!--   getLanguages() returns Language[] with code/name/qwen_code -->
<!--   PRIORITY_CODES = ["vi", "en", "ja", "zh", "zh-tw"] -->

<!-- Next.js route handler pattern (RESEARCH.md §9) -->
```typescript
export async function POST(request: Request) {
  const formData = await request.formData()
  const backendUrl = process.env.BACKEND_URL || "http://api:8000"
  const backendForm = new FormData()
  backendForm.append("file", formData.get("file") as File)
  backendForm.append("source_lang", formData.get("source_lang") as string)
  backendForm.append("target_lang", formData.get("target_lang") as string)
  const trackedAction = formData.get("tracked_changes_action")
  if (trackedAction) backendForm.append("tracked_changes_action", trackedAction as string)
  const response = await fetch(`${backendUrl}/upload`, { method: "POST", body: backendForm })
  return Response.json(await response.json(), { status: response.status })
}
```

<!-- detectTrackedChanges (Option A — jszip client-side detection) -->
```typescript
import JSZip from "jszip"

export async function detectTrackedChanges(file: File): Promise<boolean> {
  if (!file.name.toLowerCase().endsWith(".docx")) return false
  try {
    const arrayBuffer = await file.arrayBuffer()
    const zip = await JSZip.loadAsync(arrayBuffer)
    const docXml = await zip.file("word/document.xml")?.async("string")
    if (!docXml) return false
    return docXml.includes("<w:ins") || docXml.includes("<w:del")
  } catch {
    return false  // Malformed DOCX — server will handle
  }
}
```

<!-- B4 UploadForm flow -->
<!-- 1. User drops/selects file → client-side size+extension check -->
<!-- 2. If .docx: detectTrackedChanges(file) → sets hasTrackedChanges state -->
<!-- 3. handleSubmit called: if hasTrackedChanges && trackedAction === null → show modal, return -->
<!-- 4. Modal Apply Selection sets trackedAction (string), handleSubmit re-invoked with action set -->
<!-- 5. FormData built with all fields including tracked_changes_action; single POST fires -->
<!-- Key: trackedAction starts as null (not "strip") so guard is NOT dead -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: detectTrackedChanges + Next.js Upload Proxy Route + NavBar + LanguageSelect</name>
  <files>
    frontend/src/lib/detectTrackedChanges.ts
    frontend/src/app/api/upload/route.ts
    frontend/src/components/NavBar.tsx
    frontend/src/components/LanguageSelect.tsx
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 9: POST route.ts full excerpt)
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Global Shell layout, Language Selectors interaction contract, Copywriting table)
    frontend/src/lib/types.ts (Language type — code/name/qwen_code)
    frontend/src/lib/api.ts (getLanguages function — returns Language[])
  </read_first>
  <action>
Install jszip: `cd frontend && npm install jszip` (B4 Option A dependency).

Create `frontend/src/lib/detectTrackedChanges.ts` (B4 Option A — client-side detection before POST):
```typescript
import JSZip from "jszip"

/**
 * B4 Option A: Read DOCX bytes client-side and check word/document.xml
 * for <w:ins> / <w:del> elements (tracked changes markers).
 * Called on file selection — BEFORE any upload — so the modal can be shown
 * before the first POST fires.
 * Returns false for non-.docx files or malformed zip (server handles validation).
 */
export async function detectTrackedChanges(file: File): Promise<boolean> {
  if (!file.name.toLowerCase().endsWith(".docx")) return false
  try {
    const arrayBuffer = await file.arrayBuffer()
    const zip = await JSZip.loadAsync(arrayBuffer)
    const docXml = await zip.file("word/document.xml")?.async("string")
    if (!docXml) return false
    return docXml.includes("<w:ins") || docXml.includes("<w:del")
  } catch {
    // Malformed DOCX or zip read error — let the server validate
    return false
  }
}
```

Create `frontend/src/app/api/upload/route.ts` (RESEARCH.md §9 exact pattern):
```typescript
export async function POST(request: Request) {
  const formData = await request.formData()
  const file = formData.get("file") as File | null
  if (!file) {
    return Response.json({ error: "No file provided" }, { status: 400 })
  }

  const backendUrl = process.env.BACKEND_URL || "http://api:8000"
  const backendForm = new FormData()
  backendForm.append("file", file)
  backendForm.append("source_lang", (formData.get("source_lang") as string) || "auto")
  backendForm.append("target_lang", (formData.get("target_lang") as string) || "")
  const trackedAction = formData.get("tracked_changes_action")
  if (trackedAction) {
    backendForm.append("tracked_changes_action", trackedAction as string)
  }

  try {
    const response = await fetch(`${backendUrl}/upload`, {
      method: "POST",
      body: backendForm,
    })
    const data = await response.json()
    return Response.json(data, { status: response.status })
  } catch {
    return Response.json(
      { error: "Backend unavailable. Please try again." },
      { status: 503 }
    )
  }
}
```

Create `frontend/src/components/NavBar.tsx` (UI-SPEC Global Shell):
```typescript
"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useQuery } from "@tanstack/react-query"

function DashScopeHealthDot() {
  const { status } = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/api/health").then(r => r.json()),
    refetchInterval: 30_000,
    retry: 1,
  })

  const dotColor = status === "success" ? "bg-emerald-500"
    : status === "error" ? "bg-red-500"
    : "bg-amber-500"

  const label = status === "success" ? "API: reachable"
    : status === "error" ? "API: unreachable"
    : "API: checking..."

  return (
    <div className="flex items-center gap-2" title={label}>
      <div className={`h-2 w-2 rounded-full ${dotColor}`} aria-label={label} />
    </div>
  )
}

export function NavBar() {
  const pathname = usePathname()
  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center px-8">
      <div className="max-w-3xl mx-auto w-full flex items-center justify-between">
        <span className="text-[28px] font-semibold leading-none">AI Translation</span>
        <nav className="flex items-center gap-6">
          <Link
            href="/upload"
            className={`text-sm ${pathname === "/upload" ? "text-indigo-600 font-medium" : "text-slate-600 hover:text-slate-900"}`}
          >
            Upload
          </Link>
          <Link
            href="/jobs"
            className={`text-sm ${pathname?.startsWith("/jobs") ? "text-indigo-600 font-medium" : "text-slate-600 hover:text-slate-900"}`}
          >
            Jobs
          </Link>
          <DashScopeHealthDot />
        </nav>
      </div>
    </header>
  )
}
```

Create `frontend/src/components/LanguageSelect.tsx` (B5 fix — code as value, name as display):
```typescript
"use client"
import { useQuery } from "@tanstack/react-query"
import {
  Select, SelectContent, SelectGroup, SelectItem,
  SelectLabel, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { getLanguages } from "@/lib/api"
import type { Language } from "@/lib/types"

// B5: priority codes match SUPPORTED_LANGUAGES code keys in Plan 06a
const PRIORITY_CODES = ["vi", "en", "ja", "zh", "zh-tw"]

interface LanguageSelectProps {
  value: string           // language code (e.g. "vi", "en", "auto")
  onValueChange: (code: string) => void
  includeAutoDetect?: boolean
  placeholder?: string
  label: string
  disabled?: boolean
}

export function LanguageSelect({
  value, onValueChange, includeAutoDetect = false,
  placeholder, label, disabled,
}: LanguageSelectProps) {
  const { data: languages = [] } = useQuery<Language[]>({
    queryKey: ["languages"],
    queryFn: getLanguages,
    staleTime: 24 * 60 * 60 * 1000,  // 24h — static per model version (UI-SPEC)
  })

  // Exclude "auto" from the groupable list; it's rendered separately when includeAutoDetect=true
  const nonAuto = languages.filter(l => l.code !== "auto")
  const priorityLangs = nonAuto.filter(l => PRIORITY_CODES.includes(l.code))
  const otherLangs = nonAuto.filter(l => !PRIORITY_CODES.includes(l.code))

  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm text-slate-700">{label}</label>
      <Select value={value} onValueChange={onValueChange} disabled={disabled}>
        <SelectTrigger className="min-h-[48px]">
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {includeAutoDetect && (
            <SelectItem value="auto">Auto-detect</SelectItem>
          )}
          <SelectGroup>
            <SelectLabel>Recommended</SelectLabel>
            {priorityLangs.map(lang => (
              <SelectItem key={lang.code} value={lang.code}>{lang.name}</SelectItem>
            ))}
          </SelectGroup>
          <SelectGroup>
            <SelectLabel>All Languages</SelectLabel>
            {otherLangs.map(lang => (
              <SelectItem key={lang.code} value={lang.code}>{lang.name}</SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  )
}
```
  </action>
  <verify>
    <automated>
      grep -q "detectTrackedChanges" frontend/src/lib/detectTrackedChanges.ts &amp;&amp;
      grep -q "JSZip" frontend/src/lib/detectTrackedChanges.ts &amp;&amp;
      grep -q "w:ins" frontend/src/lib/detectTrackedChanges.ts &amp;&amp;
      grep -q "backendForm.append" frontend/src/app/api/upload/route.ts &amp;&amp;
      grep -q "BACKEND_URL" frontend/src/app/api/upload/route.ts &amp;&amp;
      grep -q "lang.code" frontend/src/components/LanguageSelect.tsx &amp;&amp;
      grep -q "staleTime: 24" frontend/src/components/LanguageSelect.tsx &amp;&amp;
      grep -q "PRIORITY_CODES" frontend/src/components/LanguageSelect.tsx
    </automated>
  </verify>
  <done>
    detectTrackedChanges.ts reads DOCX bytes with JSZip, checks word/document.xml for w:ins/w:del (Option A per B4).
    route.ts forwards FormData (file + source_lang + target_lang + tracked_changes_action) to FastAPI.
    LanguageSelect uses code as Select value and name as display text (B5 fix).
    Priority codes: vi, en, ja, zh, zh-tw — rendered in Recommended group.
    NavBar has Upload + Jobs links with active state, DashScope health dot.
  </done>
</task>

<task type="auto">
  <name>Task 2: UploadForm + Tracked-Changes Modal (Option A flow) + Upload Page</name>
  <files>
    frontend/src/components/UploadForm.tsx
    frontend/src/app/upload/page.tsx
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Upload Page component inventory, Interaction Contracts, Page Layout, Copywriting)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-13: tracked-changes modal 3 options)
    frontend/src/components/LanguageSelect.tsx (LanguageSelectProps interface — value is code)
    frontend/src/lib/types.ts (UploadResponse)
    frontend/src/lib/detectTrackedChanges.ts (detectTrackedChanges signature)
  </read_first>
  <action>
Create `frontend/src/components/UploadForm.tsx` with B4 Option A tracked-changes flow:

Key B4 fixes in this implementation:
1. `trackedAction` starts as `null` (NOT "strip") — guard `if (hasTrackedChanges && trackedAction === null)` is live
2. `detectTrackedChanges(file)` is called on file selection, sets `hasTrackedChanges` state
3. On submit: if hasTrackedChanges && trackedAction === null → show modal → RETURN (no POST yet)
4. Modal "Apply Selection": sets trackedAction state, then calls `submitWithAction(trackedAction)` directly
5. Modal "Cancel Upload": resets file + trackedAction to null, closes modal
6. Only ONE POST fires — after user picks their action

```typescript
"use client"
import { useState, useRef, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { LanguageSelect } from "./LanguageSelect"
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
  const [modalSelection, setModalSelection] = useState<"strip" | "preserve" | "cancel">("strip")
  // trackedAction: null = not yet decided; "strip"/"preserve" = decided by modal
  const [trackedAction, setTrackedAction] = useState<"strip" | "preserve" | null>(null)

  const handleFile = useCallback(async (f: File) => {
    const ext = getExt(f.name)
    if (!ALLOWED_EXTS.has(ext)) {
      toast({ variant: "destructive", description: "Unsupported file type. Upload a DOCX, PDF, or PPTX." })
      return
    }
    if (f.size > MAX_SIZE_BYTES) {
      toast({ variant: "destructive", description: "File too large — maximum is 25 MB." })
      return
    }
    setFile(f)
    setTrackedAction(null)  // Reset decision for new file
    setHasTrackedChanges(false)

    // B4 Option A: detect tracked changes before any upload
    const hasTC = await detectTrackedChanges(f)
    setHasTrackedChanges(hasTC)
  }, [toast])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragState("idle")
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 1) {
      toast({ variant: "destructive", description: "Upload one file at a time." })
      return
    }
    if (files[0]) handleFile(files[0])
  }, [handleFile, toast])

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragState(e.dataTransfer.items.length > 1 ? "multi" : "valid")
  }

  const canSubmit = !!file && !!targetLang && !submitting

  // Core submit function — called with a resolved action (or null for non-DOCX)
  const submitWithAction = useCallback(async (action: "strip" | "preserve" | null) => {
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
        toast({ variant: "destructive", description: data.detail || "Upload failed." })
        setSubmitting(false)
        return
      }
      router.push(`/jobs/${data.job_id}`)
    } catch {
      toast({ variant: "destructive", description: "Upload failed. Please check your connection." })
      setSubmitting(false)
    }
  }, [file, targetLang, sourceLang, router, toast])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !targetLang) return

    // B4 Option A: if tracked changes present and user hasn't decided yet → show modal
    if (hasTrackedChanges && trackedAction === null) {
      setShowTrackedModal(true)
      return  // Do NOT submit yet
    }

    await submitWithAction(trackedAction)
  }

  const dropZoneClass = dragState === "valid"
    ? "border-indigo-500 bg-indigo-50"
    : dragState === "multi"
    ? "border-red-400 bg-red-50"
    : "border-slate-300 bg-white"

  const dropZoneText = dragState === "valid" ? "Release to upload"
    : dragState === "multi" ? "One file at a time only"
    : file ? file.name
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
              <Badge variant="outline">{getExt(file.name).toUpperCase().slice(1)}</Badge>
              <span>{file.name}</span>
              <span className="text-xs text-slate-500">{formatBytes(file.size)}</span>
            </div>
          ) : (
            <>
              <CloudUpload className="h-10 w-10 text-slate-400 mb-2" />
              <p className="text-sm text-slate-700">{dropZoneText}</p>
              <p className="text-xs text-slate-500 mt-1">or click to choose a file · max 25 MB</p>
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
            ↔
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
      <Dialog
        open={showTrackedModal}
        onOpenChange={open => {
          if (!open) {
            // Dialog dismissed without Apply → treat as cancel
            setFile(null)
            setTrackedAction(null)
            setHasTrackedChanges(false)
            setShowTrackedModal(false)
          }
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
            value={modalSelection}
            onValueChange={v => setModalSelection(v as "strip" | "preserve" | "cancel")}
            className="flex flex-col gap-3 my-4"
          >
            <div className="flex items-start gap-3">
              <RadioGroupItem value="strip" id="tc-strip" />
              <Label htmlFor="tc-strip" className="cursor-pointer">
                <div className="font-medium">Remove tracked changes before translating</div>
                <div className="text-sm text-slate-500">Insertions and deletions will be stripped. The final accepted text will be translated.</div>
              </Label>
            </div>
            <div className="flex items-start gap-3">
              <RadioGroupItem value="preserve" id="tc-preserve" />
              <Label htmlFor="tc-preserve" className="cursor-pointer">
                <div className="font-medium">Preserve and translate both versions</div>
                <div className="text-sm text-slate-500">Inserted and deleted text will both be translated and kept in the output document.</div>
              </Label>
            </div>
            <div className="flex items-start gap-3">
              <RadioGroupItem value="cancel" id="tc-cancel" />
              <Label htmlFor="tc-cancel" className="cursor-pointer">
                <div className="font-medium">Cancel — I&apos;ll clean up the document first</div>
                <div className="text-sm text-slate-500">The upload will be cancelled so you can accept or reject the changes in Word.</div>
              </Label>
            </div>
          </RadioGroup>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setFile(null)
                setTrackedAction(null)
                setHasTrackedChanges(false)
                setShowTrackedModal(false)
              }}
            >
              Cancel Upload
            </Button>
            <Button
              onClick={() => {
                setShowTrackedModal(false)
                if (modalSelection === "cancel") {
                  // User chose to cancel — reset file
                  setFile(null)
                  setTrackedAction(null)
                  setHasTrackedChanges(false)
                  return
                }
                // Set the action and submit — single POST with action included
                const action = modalSelection as "strip" | "preserve"
                setTrackedAction(action)
                submitWithAction(action)
              }}
            >
              Apply Selection
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
```

Create `frontend/src/app/upload/page.tsx`:
```typescript
import { NavBar } from "@/components/NavBar"
import { UploadForm } from "@/components/UploadForm"

export default function UploadPage() {
  return (
    <>
      <NavBar />
      <main className="max-w-3xl mx-auto px-8 py-12">
        <h1 className="text-[20px] font-semibold mb-1">Translate a Document</h1>
        <p className="text-sm text-slate-500 mb-8">
          Upload a DOCX file — select languages — download the translated version.
        </p>
        <UploadForm />
      </main>
      <footer className="h-10 flex items-center justify-center text-xs text-slate-400">
        AI Translation · v0.1
      </footer>
    </>
  )
}
```
  </action>
  <verify>
    <automated>
      grep -q "min-h-\[200px\]" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "border-indigo-500" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "Tracked Changes Detected" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "RadioGroup" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "trackedAction === null" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "detectTrackedChanges" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "submitWithAction" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "Translate Document" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "Translate a Document" frontend/src/app/upload/page.tsx
    </automated>
  </verify>
  <done>
    detectTrackedChanges called on file selection (not on submit) — sets hasTrackedChanges state.
    trackedAction defaults to null (not "strip") — guard `if (hasTrackedChanges && trackedAction === null)` is live (B4 fixed).
    Modal shown BEFORE first POST; Apply Selection calls submitWithAction(action) directly (B4 fixed).
    Modal cancel resets file + trackedAction to null.
    Single POST fires — FormData built with tracked_changes_action after user chooses.
    LanguageSelect uses code as value (vi, en, auto) — UploadForm submits codes to API.
    Drop zone min-height 200px, dashed border-slate-300 at rest, border-indigo-500 + bg-indigo-50 on valid drag.
    Submit disabled until file AND targetLang both set.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → /api/upload route handler | File input from user; forwarded to FastAPI |
| tracked_changes_action field | User-selected enum value; validated server-side |
| jszip parsing → client memory | Untrusted DOCX zip parsed client-side for XML check |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-01 | Tampering | FormData file upload | mitigate | Extension + size check in UploadForm (client-side) AND FastAPI upload endpoint (server-side defense in depth) |
| T-08-02 | Tampering | tracked_changes_action value | mitigate | Backend validates enum membership; frontend only sends strip/preserve values (never "cancel") |
| T-08-03 | Denial of Service | jszip parsing large DOCX in browser | mitigate | Runs only on file selection; 25MB limit already enforced before detectTrackedChanges is called |
| T-08-04 | Information Disclosure | Backend error messages forwarded to frontend | accept | Internal PoC; detail messages from FastAPI HTTPException are informational, not sensitive |
</threat_model>

<verification>
After all tasks complete:
1. `cd frontend && npx tsc --noEmit` — no TypeScript errors in new files
2. `grep -q "trackedAction === null" frontend/src/components/UploadForm.tsx` — passes (B4 guard live)
3. `grep -q "detectTrackedChanges" frontend/src/components/UploadForm.tsx` — passes (B4 Option A)
4. `grep -q "lang.code" frontend/src/components/LanguageSelect.tsx` — passes (B5 code as value)
5. Browser: http://localhost:3000/upload shows upload form with drop zone and language selects
6. Browser: selecting a DOCX with tracked changes shows modal before any upload occurs
7. Browser: modal Cancel resets drop zone to empty state
</verification>

<success_criteria>
- detectTrackedChanges reads DOCX bytes with JSZip client-side, checks w:ins/w:del BEFORE POST
- trackedAction defaults to null — guard is live; modal appears before first POST
- Apply Selection triggers single POST with tracked_changes_action in FormData
- Modal cancel resets file to null; no upload fires
- LanguageSelect uses code as Select value (vi/en/auto) and name as label
- Drop zone has 200px min-height, dashed border at rest, indigo border+bg on valid drag-hover
- File > 25MB or wrong extension rejected with descriptive toast before any network call
- Submit button disabled until file + target language both selected
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-08-SUMMARY.md`
</output>
