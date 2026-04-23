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
autonomous: true
requirements:
  - UPLD-01
  - UPLD-02
  - UPLD-03
  - UPLD-05
  - LANG-01
  - LANG-02

must_haves:
  truths:
    - "Drop zone shows dashed border at rest, indigo border + bg on drag-hover, handles one file at a time"
    - "File rejected with toast if >25MB or unsupported format"
    - "LanguageSelect shows auto-detect as first source option, VN/EN/JA/ZH in Recommended group"
    - "Submit button is disabled until file selected AND target language selected"
    - "Tracked-changes modal appears automatically when DOCX upload detects has_tracked_changes=true"
    - "Form submit posts to /api/upload (Next.js route handler) → redirects to /jobs/[id]"
  artifacts:
    - path: "frontend/src/app/upload/page.tsx"
      provides: "Upload page with UploadForm component"
    - path: "frontend/src/app/api/upload/route.ts"
      provides: "Next.js proxy route: forwards FormData to FastAPI POST /upload"
    - path: "frontend/src/components/UploadForm.tsx"
      provides: "Drop zone + LanguageSelect + tracked-changes modal + submit"
    - path: "frontend/src/components/LanguageSelect.tsx"
      provides: "Source/target shadcn Select with Recommended group"
  key_links:
    - from: "frontend/src/components/UploadForm.tsx"
      to: "frontend/src/app/api/upload/route.ts"
      via: "fetch POST /api/upload with FormData"
    - from: "frontend/src/app/api/upload/route.ts"
      to: "FastAPI POST /upload"
      via: "fetch(backendUrl + '/upload', {body: backendForm})"
    - from: "tracked-changes modal"
      to: "tracked_changes_action form field"
      via: "RadioGroup selection → appended to FormData before submit"
---

<objective>
Build the upload page: drag-and-drop zone, source/target language selectors, tracked-changes modal, and the Next.js proxy route handler. File selection, validation, and submission all work per UI-SPEC interaction contracts.

Purpose: The primary user-facing entry point. Without this, users cannot submit translation jobs.
Output: /upload route fully functional: user can drag-drop a DOCX, pick languages, handle tracked changes, submit and be redirected to the job status page.
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
<!-- UI-SPEC exact interaction contracts and copy -->

Drop zone states (UI-SPEC Interaction Contracts):
  Idle: dashed border-slate-300, cloud-upload icon, "Drop your DOCX, PDF, or PPTX here"
  Drag-hover (valid single file): border-indigo-500, bg-indigo-50, "Release to upload"
  Drag-hover (multi-file): border-red-400, bg-red-50, "One file at a time only"
  File selected: filename chip + format badge + size text, drop zone collapses to 40px
  Rejected-format: Toast "Unsupported file type. Upload a DOCX, PDF, or PPTX."
  Rejected-too-large: Toast "File too large — maximum is 25 MB."
  Rejected-multi: Toast "Upload one file at a time."

Tracked-changes modal (D-13 / UI-SPEC):
  Title: "Tracked Changes Detected"
  Body: "This document has unresolved tracked changes. How would you like to handle them?"
  RadioGroup options:
    strip: "Remove tracked changes before translating"
    preserve: "Preserve and translate both versions"
    cancel: "Cancel — I'll clean up the document first"
  Confirm CTA: "Apply Selection"
  Cancel: "Cancel Upload" → resets file, closes dialog

Language selectors (UI-SPEC):
  Source: default "Auto-detect"; grouped: [Auto-detect] then [Recommended: VN/EN/JA/ZH/ZH-TW] then [All Languages: A-Z]
  Target: no default, required; placeholder "Select target language"; same groups, no Auto-detect
  Swap button: ghost icon-only, ↔ icon, disabled when source=Auto-detect, tooltip "Swap languages"

Page copy (UI-SPEC Copywriting):
  heading: "Translate a Document"
  subheading: "Upload a DOCX file — select languages — download the translated version."
  CTA: "Translate Document"

Next.js route handler pattern (RESEARCH.md §9):
```typescript
export async function POST(request: Request) {
  const formData = await request.formData()
  const backendUrl = process.env.BACKEND_URL || "http://api:8000"
  const backendForm = new FormData()
  backendForm.append("file", formData.get("file") as File)
  backendForm.append("source_lang", formData.get("source_lang") as string)
  backendForm.append("target_lang", formData.get("target_lang") as string)
  const response = await fetch(`${backendUrl}/upload`, { method: "POST", body: backendForm })
  return Response.json(await response.json(), { status: response.status })
}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Next.js Upload Proxy Route + NavBar + LanguageSelect</name>
  <files>
    frontend/src/app/api/upload/route.ts
    frontend/src/components/NavBar.tsx
    frontend/src/components/LanguageSelect.tsx
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 9: POST route.ts full excerpt)
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Global Shell layout, Language Selectors interaction contract, Copywriting table)
    frontend/src/lib/types.ts (LanguagesResponse type)
    frontend/src/lib/api.ts (getLanguages function)
  </read_first>
  <action>
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
  } catch (err) {
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
  // Poll /api/health every 30s to show DashScope reachability
  // Simple implementation: green dot on success, amber on loading, red on error
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
    : status === "error" ? "API: unreachable — check your connection or API key"
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

Create `frontend/src/components/LanguageSelect.tsx` (UI-SPEC language picker):
```typescript
"use client"
import { useQuery } from "@tanstack/react-query"
import {
  Select, SelectContent, SelectGroup, SelectItem,
  SelectLabel, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { getLanguages } from "@/lib/api"

const PRIORITY_LANGUAGES = [
  "Vietnamese", "English", "Japanese",
  "Chinese (Simplified)", "Chinese (Traditional)",
]

interface LanguageSelectProps {
  value: string
  onValueChange: (value: string) => void
  includeAutoDetect?: boolean
  placeholder?: string
  label: string
  disabled?: boolean
}

export function LanguageSelect({
  value, onValueChange, includeAutoDetect = false,
  placeholder, label, disabled,
}: LanguageSelectProps) {
  const { data: languages = [] } = useQuery({
    queryKey: ["languages"],
    queryFn: getLanguages,
    staleTime: 24 * 60 * 60 * 1000,  // 24h — static per model version (UI-SPEC)
  })

  const otherLanguages = languages.filter(l => !PRIORITY_LANGUAGES.includes(l))

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
            {PRIORITY_LANGUAGES.map(lang => (
              <SelectItem key={lang} value={lang}>{lang}</SelectItem>
            ))}
          </SelectGroup>
          <SelectGroup>
            <SelectLabel>All Languages</SelectLabel>
            {otherLanguages.map(lang => (
              <SelectItem key={lang} value={lang}>{lang}</SelectItem>
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
      grep -q "backendForm.append" frontend/src/app/api/upload/route.ts &amp;&amp;
      grep -q "BACKEND_URL" frontend/src/app/api/upload/route.ts &amp;&amp;
      grep -q "staleTime: 24" frontend/src/components/LanguageSelect.tsx &amp;&amp;
      grep -q "PRIORITY_LANGUAGES" frontend/src/components/LanguageSelect.tsx &amp;&amp;
      grep -q "Auto-detect" frontend/src/components/LanguageSelect.tsx
    </automated>
  </verify>
  <done>
    route.ts forwards FormData (file + source_lang + target_lang + tracked_changes_action) to FastAPI.
    LanguageSelect loads languages from /languages with 24h stale time, groups into Recommended + All Languages.
    Priority languages: Vietnamese, English, Japanese, Chinese (Simplified), Chinese (Traditional).
    NavBar has Upload + Jobs links with active state, DashScope health dot.
  </done>
</task>

<task type="auto">
  <name>Task 2: UploadForm + Tracked-Changes Modal + Upload Page</name>
  <files>
    frontend/src/components/UploadForm.tsx
    frontend/src/app/upload/page.tsx
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Upload Page component inventory, Interaction Contracts, Page Layout, Copywriting)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-13: tracked-changes modal 3 options)
    frontend/src/components/LanguageSelect.tsx (LanguageSelectProps interface)
    frontend/src/lib/types.ts (UploadResponse)
  </read_first>
  <action>
Create `frontend/src/components/UploadForm.tsx` implementing full UI-SPEC upload form:
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

  // Tracked-changes modal (D-13)
  const [showTrackedModal, setShowTrackedModal] = useState(false)
  const [trackedAction, setTrackedAction] = useState("strip")
  const pendingFile = useRef<File | null>(null)

  const handleFile = useCallback((f: File) => {
    const ext = getExt(f.name)
    if (!ALLOWED_EXTS.has(ext)) {
      toast({ variant: "destructive", description: "Unsupported file type. Upload a DOCX, PDF, or PPTX." })
      return
    }
    if (f.size > MAX_SIZE_BYTES) {
      toast({ variant: "destructive", description: "File too large — maximum is 25 MB." })
      return
    }
    // Tracked-changes detection happens server-side on upload; show modal if backend says so.
    // For now, set the file directly; after real upload, modal is shown if has_tracked_changes=true.
    setFile(f)
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !targetLang) return

    setSubmitting(true)
    try {
      const formData = new FormData()
      formData.append("file", file)
      formData.append("source_lang", sourceLang)
      formData.append("target_lang", targetLang)
      if (trackedAction && showTrackedModal === false) {
        // Only append if user has made a tracked-changes choice
      }

      const res = await fetch("/api/upload", { method: "POST", body: formData })
      const data = await res.json()

      if (!res.ok) {
        toast({ variant: "destructive", description: data.detail || "Upload failed." })
        setSubmitting(false)
        return
      }

      // If backend signals tracked changes and we haven't shown the modal yet
      if (data.has_tracked_changes && !trackedAction) {
        pendingFile.current = file
        setShowTrackedModal(true)
        setSubmitting(false)
        return
      }

      router.push(`/jobs/${data.job_id}`)
    } catch {
      toast({ variant: "destructive", description: "Upload failed. Please check your connection." })
      setSubmitting(false)
    }
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
              <span className={`text-xs ${file.size > MAX_SIZE_BYTES ? "text-red-500" : "text-slate-500"}`}>
                {formatBytes(file.size)}
              </span>
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

      {/* Tracked-changes modal (D-13) */}
      <Dialog open={showTrackedModal} onOpenChange={open => { if (!open) { setFile(null); setShowTrackedModal(false) } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Tracked Changes Detected</DialogTitle>
            <DialogDescription>
              This document has unresolved tracked changes. How would you like to handle them?
            </DialogDescription>
          </DialogHeader>
          <RadioGroup value={trackedAction} onValueChange={setTrackedAction} className="flex flex-col gap-3 my-4">
            <div className="flex items-start gap-3">
              <RadioGroupItem value="strip" id="tc-strip" />
              <Label htmlFor="tc-strip" className="cursor-pointer">
                <div className="font-medium">Remove tracked changes before translating</div>
                <div className="text-sm text-slate-500">Tracked insertions and deletions will be stripped. The final accepted text will be translated.</div>
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
            <Button variant="outline" onClick={() => { setFile(null); setShowTrackedModal(false) }}>
              Cancel Upload
            </Button>
            <Button onClick={() => {
              if (trackedAction === "cancel") { setFile(null); setShowTrackedModal(false); return }
              setShowTrackedModal(false)
              // Re-submit with trackedAction set
            }}>
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
      grep -q "Translate Document" frontend/src/components/UploadForm.tsx &amp;&amp;
      grep -q "Translate a Document" frontend/src/app/upload/page.tsx
    </automated>
  </verify>
  <done>
    Drop zone min-height 200px, dashed border-slate-300 at rest, border-indigo-500 + bg-indigo-50 on valid drag.
    Multi-file drop shows "border-red-400" state and "Upload one file at a time" toast.
    Submit button disabled until file AND targetLang both set.
    Tracked-changes modal with three RadioGroup options and "Apply Selection" / "Cancel Upload" buttons.
    Page heading "Translate a Document", subheading copy per UI-SPEC.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser → /api/upload route handler | File input from user; forwarded to FastAPI |
| tracked_changes_action field | User-selected enum value; validated server-side |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-08-01 | Tampering | FormData file upload | mitigate | Extension + size check in UploadForm (client-side) AND FastAPI upload endpoint (server-side defense in depth) |
| T-08-02 | Tampering | tracked_changes_action value | mitigate | Backend validates enum membership; frontend only sends strip/preserve values |
| T-08-03 | Information Disclosure | Backend error messages forwarded to frontend | accept | Internal PoC; detail messages from FastAPI HTTPException are informational, not sensitive |
</threat_model>

<verification>
After all tasks complete:
1. `cd frontend && npx tsc --noEmit` — no TypeScript errors in new files
2. `grep -q "min-h-\[200px\]" frontend/src/components/UploadForm.tsx` — passes
3. `grep -q "Tracked Changes Detected" frontend/src/components/UploadForm.tsx` — passes
4. Browser: http://localhost:3000/upload shows upload form with drop zone and language selects
5. Browser: dragging a DOCX onto the drop zone shows indigo highlight state
</verification>

<success_criteria>
- Drop zone has 200px min-height, dashed border at rest, indigo border+bg on valid drag-hover
- File > 25MB or wrong extension rejected with descriptive toast before any network call
- Multi-file drop rejected with toast, no file set
- Tracked-changes modal appears with 3 RadioGroup options; cancel resets file
- Submit button disabled until file + target language both selected
- Form submission POSTs to /api/upload (Next.js route) which forwards to FastAPI
- Redirect to /jobs/[id] on successful upload
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-08-SUMMARY.md`
</output>
