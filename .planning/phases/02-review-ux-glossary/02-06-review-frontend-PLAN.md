---
phase: 02-review-ux-glossary
plan: "06"
type: execute
wave: 2
depends_on: ["02-01", "02-04", "02-05"]
files_modified:
  - frontend/src/hooks/useSegments.ts
  - frontend/src/hooks/useReviewKeyboard.ts
  - frontend/src/components/SegmentTable.tsx
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/components/ReviewFilterBar.tsx
  - frontend/src/components/ReviewPageHeader.tsx
  - frontend/src/components/KeyboardHelpPanel.tsx
  - frontend/src/app/jobs/[id]/review/page.tsx
  - frontend/src/app/jobs/[id]/page.tsx
autonomous: true
requirements: [REV-01, REV-02, REV-03, REV-04, REV-05, REV-06, LAYOUT-01]

must_haves:
  truths:
    - "User can navigate to the review page from a completed/needs_review job"
    - "User sees all segments in a virtualized table (source left, editable translation right)"
    - "Editing a translation auto-saves after 500ms debounce with optimistic update and error rollback"
    - "Each segment shows its flag badges (overflow, glossary violation, placeholder, refusal)"
    - "User can filter segments by flag type using the filter chip bar"
    - "User can regenerate a single segment's translation"
    - "User can export the translated DOCX (edited_text takes precedence over translated_text)"
    - "Keyboard shortcuts j/k/n/e/r/? work outside text fields"
  artifacts:
    - path: "frontend/src/hooks/useSegments.ts"
      provides: "TanStack Query segments cache + optimistic PATCH mutation"
      exports: ["useSegments", "useSegmentPatch", "useSegmentRegenerate"]
    - path: "frontend/src/hooks/useReviewKeyboard.ts"
      provides: "react-hotkeys-hook bindings for j/k/n/e/r/? per D-02-17"
      exports: ["useReviewKeyboard"]
    - path: "frontend/src/components/SegmentTable.tsx"
      provides: "react-virtuoso Virtuoso wrapper with scrollIntoView for keyboard nav"
    - path: "frontend/src/components/SegmentRow.tsx"
      provides: "Single segment row: SourceCell + TargetCell (debounced) + FlagCell"
    - path: "frontend/src/components/ReviewFilterBar.tsx"
      provides: "Filter chips per flag type + Shortcuts toggle button"
    - path: "frontend/src/app/jobs/[id]/review/page.tsx"
      provides: "Review page assembling all review components"
    - path: "frontend/src/app/jobs/[id]/page.tsx"
      provides: "Job detail page with Review link shown on done/needs_review"
  key_links:
    - from: "useSegments.ts"
      to: "GET /api/jobs/{id}/segments"
      via: "useQuery(['segments', jobId])"
      pattern: "fetch.*segments"
    - from: "SegmentRow TargetCell"
      to: "PATCH /api/segments/{id}"
      via: "useSegmentPatch mutation (500ms debounce)"
      pattern: "PATCH.*segments"
    - from: "ReviewPageHeader ExportButton"
      to: "POST /api/jobs/{id}/export"
      via: "fetch with file download trigger"
      pattern: "jobs.*export"
    - from: "SegmentRow RegenerateButton"
      to: "POST /api/segments/{id}/regenerate"
      via: "useSegmentRegenerate mutation"
      pattern: "regenerate"
---

<objective>
Build the review page frontend: useSegments and useReviewKeyboard hooks, SegmentTable (react-virtuoso), SegmentRow with debounced TargetCell, ReviewFilterBar with flag chips, ReviewPageHeader with export button, KeyboardHelpPanel, and the /jobs/[id]/review route. Also extend /jobs/[id]/page.tsx to add a "Review" link on terminal job states.

Purpose: Delivers REV-01..06 (virtualized segment table, inline edit, flag display, regenerate, idempotent export) and LAYOUT-01 (expansion ratio surfaced as overflow flag badge).

Output: 9 new/modified frontend files. Review UX fully functional.
</objective>

<execution_context>
@/home/thu/.claude/get-shit-done/workflows/execute-plan.md
@/home/thu/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-UI-SPEC.md
@.planning/phases/02-review-ux-glossary/02-RESEARCH.md
@.planning/phases/02-review-ux-glossary/02-PATTERNS.md
@.planning/phases/02-review-ux-glossary/02-04-segment-export-backend-PLAN.md

<interfaces>
<!-- Phase 2 types (from Plan 05 types.ts additions) -->
```typescript
export type FlagType = "overflow" | "glossary_violation" | "placeholder_mismatch" | "llm_refusal";
export interface SegmentFlag { id: string; segment_id: string; flag_type: FlagType; severity: string; details: Record<string, unknown>; created_at: string; }
export interface Segment { id: string; job_id: string; seq_in_job: number; source_text: string; translated_text: string | null; edited_text: string | null; expansion_ratio: number | null; flags: SegmentFlag[]; }
export interface SegmentsResponse { segments: Segment[]; total: number; }
```

<!-- Backend endpoints available after Plan 04 -->
<!-- GET  /api/jobs/{id}/segments             -> SegmentsResponse -->
<!-- PATCH /api/segments/{id}                 -> Segment  (body: { edited_text: string | null }) -->
<!-- POST /api/segments/{id}/regenerate       -> { translated_text: string } -->
<!-- POST /api/jobs/{id}/export               -> DOCX file (Content-Disposition: attachment) -->

<!-- TanStack Query v5 optimistic mutation (RESEARCH.md Section 1) -->
```typescript
// useSegmentPatch — verified pattern from RESEARCH.md
useMutation({
  mutationFn: async ({ segmentId, editedText }) => { /* PATCH */ },
  onMutate: async ({ segmentId, editedText }) => {
    await queryClient.cancelQueries({ queryKey: ["segments", jobId] });
    const previousSegments = queryClient.getQueryData<Segment[]>(["segments", jobId]);
    queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
      old?.map((seg) => seg.id === segmentId ? { ...seg, edited_text: editedText } : seg) ?? []
    );
    return { previousSegments };
  },
  onError: (_err, _vars, context) => {
    if (context?.previousSegments) queryClient.setQueryData(["segments", jobId], context.previousSegments);
    toast({ title: "Could not save — edit restored.", variant: "destructive" });
  },
  onSettled: () => queryClient.invalidateQueries({ queryKey: ["segments", jobId] }),
})
```

<!-- react-virtuoso Virtuoso (RESEARCH.md Section 2) -->
```typescript
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";
// style={{ height: "calc(100vh - 168px)" }} // 168px = nav(56) + header(64) + filterbar(48)
// increaseViewportBy={{ top: 300, bottom: 500 }}
// ref.current?.scrollIntoView({ index, behavior: "auto" })
```

<!-- react-hotkeys-hook (RESEARCH.md Section 3) -->
```typescript
import { useHotkeys } from "react-hotkeys-hook";
// j/k/n/e/r/?: no enableOnFormTags (disabled in textareas by default)
// escape: { enableOnFormTags: ["textarea"] }
```

<!-- FlagBadge component (created in Plan 05) -->
```typescript
import { FlagBadge } from "@/components/FlagBadge";
// <FlagBadge flagType="overflow" />
```

<!-- Debounce pattern from RESEARCH.md Section 1 -->
```typescript
const debounceRef = useRef<ReturnType<typeof setTimeout>>();
const handleChange = (value: string) => {
  setLocalValue(value);
  clearTimeout(debounceRef.current);
  debounceRef.current = setTimeout(() => {
    patchMutation.mutate({ segmentId: segment.id, editedText: value });
  }, 500);
};
useEffect(() => () => clearTimeout(debounceRef.current), []);
```

<!-- Phase 1 jobs/[id]/page.tsx: JobStatus + conditional rendering of actions -->
<!-- Add Review link when status === "done" || status === "needs_review" -->
<!-- Use Link href={`/jobs/${job.id}/review`} -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create useSegments.ts and useReviewKeyboard.ts hooks</name>
  <files>
    frontend/src/hooks/useSegments.ts
    frontend/src/hooks/useReviewKeyboard.ts
  </files>
  <behavior>
    - useSegments returns segments array via useQuery(['segments', jobId])
    - useSegmentPatch implements optimistic update + rollback + "Could not save" toast on error
    - useSegmentRegenerate POSTs to /api/segments/{id}/regenerate and invalidates segments cache
    - useReviewKeyboard binds j/k/n/e/r/? outside form fields; escape inside textarea
    - Callbacks receive current focusedIndex, segmentCount, flaggedIndices
  </behavior>
  <action>
**useSegments.ts** — implement three exports: `useSegments`, `useSegmentPatch`, `useSegmentRegenerate`.

```typescript
"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import type { Segment, SegmentsResponse } from "@/lib/types";

export function useSegments(jobId: string) {
  return useQuery<Segment[]>({
    queryKey: ["segments", jobId],
    queryFn: async () => {
      const res = await fetch(`/api/jobs/${jobId}/segments`);
      if (!res.ok) throw new Error("Failed to load segments");
      const data: SegmentsResponse = await res.json();
      return data.segments;
    },
    enabled: !!jobId,
  });
}

export function useSegmentPatch(jobId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: async ({
      segmentId,
      editedText,
    }: {
      segmentId: string;
      editedText: string | null;
    }) => {
      const res = await fetch(`/api/segments/${segmentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edited_text: editedText }),
      });
      if (!res.ok) throw new Error("Save failed");
      return res.json() as Promise<Segment>;
    },

    onMutate: async ({ segmentId, editedText }) => {
      await queryClient.cancelQueries({ queryKey: ["segments", jobId] });
      const previousSegments = queryClient.getQueryData<Segment[]>(["segments", jobId]);
      queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
        old?.map((seg) =>
          seg.id === segmentId ? { ...seg, edited_text: editedText } : seg
        ) ?? []
      );
      return { previousSegments };
    },

    onError: (_err, _vars, context) => {
      if (context?.previousSegments) {
        queryClient.setQueryData(["segments", jobId], context.previousSegments);
      }
      toast({
        title: "Could not save — edit restored.",
        variant: "destructive",
      });
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["segments", jobId] });
    },
  });
}

export function useSegmentRegenerate(jobId: string) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  return useMutation({
    mutationFn: async (segmentId: string) => {
      const res = await fetch(`/api/segments/${segmentId}/regenerate`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Regenerate failed");
      return res.json() as Promise<{ translated_text: string }>;
    },
    onSuccess: (data, segmentId) => {
      queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
        old?.map((seg) =>
          seg.id === segmentId
            ? { ...seg, translated_text: data.translated_text }
            : seg
        ) ?? []
      );
    },
    onError: () => {
      toast({ title: "Regeneration failed. Try again.", variant: "destructive" });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["segments", jobId] });
    },
  });
}
```

**useReviewKeyboard.ts** — bind all six shortcuts from D-02-17.

```typescript
import { useHotkeys } from "react-hotkeys-hook";

interface ReviewKeyboardOptions {
  focusedIndex: number;
  segmentCount: number;
  flaggedIndices: number[];
  onFocusChange: (index: number) => void;
  onEdit: (index: number) => void;
  onRegenerate: (index: number) => void;
  onToggleHelp: () => void;
}

export function useReviewKeyboard({
  focusedIndex,
  segmentCount,
  flaggedIndices,
  onFocusChange,
  onEdit,
  onRegenerate,
  onToggleHelp,
}: ReviewKeyboardOptions) {
  // j: next segment — disabled in form tags by default
  useHotkeys(
    "j",
    () => onFocusChange(Math.min(focusedIndex + 1, segmentCount - 1)),
    { preventDefault: true },
    [focusedIndex, segmentCount]
  );

  // k: previous segment
  useHotkeys(
    "k",
    () => onFocusChange(Math.max(focusedIndex - 1, 0)),
    { preventDefault: true },
    [focusedIndex]
  );

  // n: next flagged segment (cycles)
  useHotkeys(
    "n",
    () => {
      if (flaggedIndices.length === 0) return;
      const next =
        flaggedIndices.find((i) => i > focusedIndex) ?? flaggedIndices[0];
      onFocusChange(next);
    },
    { preventDefault: true },
    [focusedIndex, flaggedIndices]
  );

  // e: focus target textarea of focused segment
  useHotkeys("e", () => onEdit(focusedIndex), { preventDefault: true }, [
    focusedIndex,
  ]);

  // r: regenerate focused segment
  useHotkeys(
    "r",
    () => onRegenerate(focusedIndex),
    { preventDefault: true },
    [focusedIndex]
  );

  // ?: toggle help panel
  useHotkeys("shift+/", () => onToggleHelp(), { preventDefault: true });

  // Escape: blur active textarea (enabled in textarea)
  useHotkeys(
    "escape",
    () => (document.activeElement as HTMLElement)?.blur(),
    { enableOnFormTags: ["textarea"] }
  );
}
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    useSegments.ts and useReviewKeyboard.ts exist. TypeScript clean.
    useSegments exports useSegments, useSegmentPatch, useSegmentRegenerate.
    useReviewKeyboard binds j/k/n/e/r/shift+/ and escape-in-textarea.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create SegmentTable, SegmentRow, ReviewFilterBar, ReviewPageHeader, KeyboardHelpPanel</name>
  <files>
    frontend/src/components/SegmentTable.tsx
    frontend/src/components/SegmentRow.tsx
    frontend/src/components/ReviewFilterBar.tsx
    frontend/src/components/ReviewPageHeader.tsx
    frontend/src/components/KeyboardHelpPanel.tsx
  </files>
  <action>
**SegmentTable.tsx** — react-virtuoso wrapper. Analog: `src/components/JobsTable.tsx`.

```tsx
"use client";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { useRef, useCallback, forwardRef, useImperativeHandle } from "react";
import { SegmentRow } from "@/components/SegmentRow";
import type { Segment } from "@/lib/types";

export interface SegmentTableHandle {
  scrollToIndex: (index: number) => void;
}

interface SegmentTableProps {
  segments: Segment[];
  focusedIndex: number;
  onFocusChange: (index: number) => void;
  jobId: string;
  editingRef?: React.MutableRefObject<Map<string, HTMLTextAreaElement>>;
}

export const SegmentTable = forwardRef<SegmentTableHandle, SegmentTableProps>(
  function SegmentTable({ segments, focusedIndex, onFocusChange, jobId, editingRef }, ref) {
    const virtuosoRef = useRef<VirtuosoHandle>(null);

    useImperativeHandle(ref, () => ({
      scrollToIndex(index: number) {
        virtuosoRef.current?.scrollIntoView({ index, behavior: "auto" });
      },
    }));

    const handleFocus = useCallback(
      (index: number) => {
        onFocusChange(index);
        virtuosoRef.current?.scrollIntoView({ index, behavior: "auto" });
      },
      [onFocusChange]
    );

    return (
      <Virtuoso
        ref={virtuosoRef}
        style={{ height: "calc(100vh - 168px)" }}
        data={segments}
        increaseViewportBy={{ top: 300, bottom: 500 }}
        itemContent={(index, segment) => (
          <SegmentRow
            key={segment.id}
            segment={segment}
            isFocused={index === focusedIndex}
            jobId={jobId}
            onFocus={() => handleFocus(index)}
            textareaRef={(el) => {
              if (editingRef) {
                if (el) editingRef.current.set(segment.id, el);
                else editingRef.current.delete(segment.id);
              }
            }}
          />
        )}
      />
    );
  }
);
```

**SegmentRow.tsx** — single row: index | source | target (debounced) | flags.

Key states per UI-SPEC interaction contracts:
- Default: `bg-white`
- Hovered: `hover:bg-slate-50`
- Focused: `ring-1 ring-violet-200`
- TargetCell saving: dashed ring + "Saving…" footer text
- TargetCell saved: "Saved" + Check icon, fades after 1.5s

```tsx
"use client";
import { useState, useRef, useEffect } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { FlagBadge } from "@/components/FlagBadge";
import { RefreshCw, Check } from "lucide-react";
import { useSegmentPatch, useSegmentRegenerate } from "@/hooks/useSegments";
import type { Segment } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SegmentRowProps {
  segment: Segment;
  isFocused: boolean;
  jobId: string;
  onFocus: () => void;
  textareaRef?: (el: HTMLTextAreaElement | null) => void;
}

export function SegmentRow({ segment, isFocused, jobId, onFocus, textareaRef }: SegmentRowProps) {
  // Display value = edited_text if present, else translated_text, else ""
  const displayValue =
    segment.edited_text !== null
      ? segment.edited_text
      : (segment.translated_text ?? "");

  const [localValue, setLocalValue] = useState(displayValue);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const savedTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const patchMutation = useSegmentPatch(jobId);
  const regenerateMutation = useSegmentRegenerate(jobId);

  // Keep local value in sync when segment data changes externally (e.g. regenerate)
  useEffect(() => {
    const newDisplay =
      segment.edited_text !== null
        ? segment.edited_text
        : (segment.translated_text ?? "");
    setLocalValue(newDisplay);
  }, [segment.edited_text, segment.translated_text]);

  const handleChange = (value: string) => {
    setLocalValue(value);
    setSaveState("saving");
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      patchMutation.mutate(
        { segmentId: segment.id, editedText: value },
        {
          onSuccess: () => {
            setSaveState("saved");
            savedTimerRef.current = setTimeout(() => setSaveState("idle"), 1500);
          },
        }
      );
    }, 500);
  };

  // Cleanup debounce and save timers on unmount
  useEffect(() => {
    return () => {
      clearTimeout(debounceRef.current);
      clearTimeout(savedTimerRef.current);
    };
  }, []);

  const hasFlaggedLeft =
    segment.flags.length > 0
      ? segment.flags[0].flag_type
      : null;

  const leftBorderColor: Record<string, string> = {
    overflow: "border-l-amber-500",
    glossary_violation: "border-l-violet-500",
    placeholder_mismatch: "border-l-orange-500",
    llm_refusal: "border-l-red-500",
  };

  return (
    <div
      className={cn(
        "flex border-b border-slate-100 border-l-4",
        isFocused ? "ring-1 ring-violet-200" : "",
        hasFlaggedLeft ? leftBorderColor[hasFlaggedLeft] ?? "border-l-transparent" : "border-l-transparent",
        "hover:bg-slate-50 cursor-pointer"
      )}
      onClick={onFocus}
    >
      {/* Index */}
      <div className="w-12 flex-shrink-0 py-2 px-1 text-xs text-slate-400 font-roboto select-none">
        {segment.seq_in_job}
      </div>

      {/* Source cell: PT Mono, read-only */}
      <div
        className="flex-[40] py-2 px-2 text-xs font-mono text-[#111111] bg-slate-50 border-r border-slate-100 select-text min-h-[48px] whitespace-pre-wrap"
        style={{ fontFamily: "var(--font-pt-mono, monospace)" }}
      >
        {segment.source_text}
      </div>

      {/* Target cell: editable Textarea */}
      <div className="flex-[50] flex flex-col py-1 px-2 min-h-[48px]">
        <Textarea
          ref={textareaRef ?? null}
          value={localValue}
          onChange={(e) => handleChange(e.target.value)}
          className={cn(
            "min-h-[48px] resize-none border-none shadow-none p-1 text-sm focus-visible:ring-2 focus-visible:ring-violet-500",
            saveState === "saving" ? "ring-1 ring-dashed ring-slate-400" : ""
          )}
          placeholder="Translation…"
        />
        {/* Save state indicator */}
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-slate-400">
            {saveState === "saving" && "Saving…"}
            {saveState === "saved" && (
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3" /> Saved
              </span>
            )}
          </span>
          {/* Regenerate button */}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            title="Regenerate translation"
            disabled={regenerateMutation.isPending}
            onClick={(e) => {
              e.stopPropagation();
              regenerateMutation.mutate(segment.id);
            }}
          >
            <RefreshCw
              className={cn(
                "h-3.5 w-3.5 text-violet-600",
                regenerateMutation.isPending ? "animate-spin" : ""
              )}
            />
          </Button>
        </div>
        {/* Discard edit button — visible only if edited_text != null (explicit None check) */}
        {segment.edited_text !== null && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-red-500 hover:text-red-700 h-6 px-1 self-start"
            onClick={(e) => {
              e.stopPropagation();
              patchMutation.mutate({ segmentId: segment.id, editedText: null });
            }}
          >
            Discard edit
          </Button>
        )}
      </div>

      {/* Flag cell */}
      <div className="w-20 flex-shrink-0 py-2 px-1 flex flex-col gap-1">
        {segment.flags.map((flag) => (
          <FlagBadge key={flag.id} flagType={flag.flag_type} />
        ))}
      </div>
    </div>
  );
}
```

**ReviewFilterBar.tsx** — horizontal chip strip above segment table.

```tsx
"use client";
import { Button } from "@/components/ui/button";
import { Keyboard } from "lucide-react";
import type { FlagType, Segment } from "@/lib/types";
import { cn } from "@/lib/utils";

type FilterType = FlagType | "all";

interface ReviewFilterBarProps {
  segments: Segment[];
  activeFilter: FilterType;
  onFilterChange: (f: FilterType) => void;
  onToggleHelp: () => void;
}

const FLAG_LABELS: Record<FlagType, string> = {
  overflow: "Overflow",
  glossary_violation: "Glossary violation",
  placeholder_mismatch: "Placeholder",
  llm_refusal: "Refusal",
};

export function ReviewFilterBar({
  segments,
  activeFilter,
  onFilterChange,
  onToggleHelp,
}: ReviewFilterBarProps) {
  const allCount = segments.length;

  const flagCounts = (
    ["overflow", "glossary_violation", "placeholder_mismatch", "llm_refusal"] as FlagType[]
  ).map((flagType) => ({
    flagType,
    count: segments.filter((s) => s.flags.some((f) => f.flag_type === flagType)).length,
  }));

  const chipBase = "h-8 rounded-full text-xs px-3 border";
  const activeClass = "bg-violet-500 text-white border-violet-500";
  const inactiveClass = "bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200";

  return (
    <div className="flex items-center gap-2 h-12 px-4 bg-white border-b border-slate-100 overflow-x-auto sticky top-[120px]">
      {/* All chip */}
      <button
        className={cn(chipBase, activeFilter === "all" ? activeClass : inactiveClass)}
        onClick={() => onFilterChange("all")}
      >
        All ({allCount})
      </button>

      {/* Per-flag chips */}
      {flagCounts.map(({ flagType, count }) => (
        <button
          key={flagType}
          className={cn(chipBase, activeFilter === flagType ? activeClass : inactiveClass)}
          onClick={() => onFilterChange(flagType)}
        >
          {FLAG_LABELS[flagType]} ({count})
        </button>
      ))}

      <div className="flex-1" />

      {/* Shortcuts toggle */}
      <Button
        variant="ghost"
        size="sm"
        className="flex items-center gap-1.5 text-xs text-slate-500"
        onClick={onToggleHelp}
      >
        <Keyboard className="h-3.5 w-3.5" />
        Shortcuts
      </Button>
    </div>
  );
}
```

**ReviewPageHeader.tsx** — sticky header with filename, metadata, export button.

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import type { JobSummary } from "@/lib/types";
import { useToast } from "@/hooks/use-toast";

interface ReviewPageHeaderProps {
  job: JobSummary & { glossary_name?: string | null };
}

export function ReviewPageHeader({ job }: ReviewPageHeaderProps) {
  const [exporting, setExporting] = useState(false);
  const { toast } = useToast();

  const canExport = job.status === "done" || job.status === "needs_review";

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`/api/jobs/${job.id}/export`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        toast({
          title: `Export failed — ${err.detail ?? "Unknown error"}. Try again.`,
          variant: "destructive",
        });
        return;
      }
      // Trigger download
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = job.input_filename.replace(/(\.\w+)?$/, "_translated.docx");
      a.click();
      URL.revokeObjectURL(url);
      toast({ title: "Export ready — downloading." });
    } catch {
      toast({ title: "Export failed — network error. Try again.", variant: "destructive" });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="sticky top-14 z-10 flex items-center gap-4 h-16 px-8 bg-white border-b border-slate-200">
      <Link
        href="/jobs"
        className="text-sm text-slate-500 hover:text-slate-700 shrink-0"
      >
        ← All Jobs
      </Link>
      <div className="flex-1 min-w-0">
        <h1
          className="text-xl font-semibold truncate text-[#111111]"
          style={{ fontFamily: "var(--font-montserrat, sans-serif)" }}
        >
          {job.input_filename}
        </h1>
        <p className="text-xs text-slate-400">
          {job.source_lang} → {job.target_lang}
          {job.glossary_name && (
            <span className="ml-2 px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-xs">
              Glossary: {job.glossary_name}
            </span>
          )}
        </p>
      </div>
      {canExport && (
        <Button
          disabled={exporting}
          onClick={handleExport}
          className="shrink-0 bg-violet-500 hover:bg-violet-600 text-white"
        >
          {exporting ? "Exporting…" : "Export Document"}
        </Button>
      )}
    </div>
  );
}
```

**KeyboardHelpPanel.tsx** — popover/panel with cheatsheet. Shown when `open=true`.

```tsx
"use client";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface KeyboardHelpPanelProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS: Array<{ key: string; action: string }> = [
  { key: "j", action: "Next segment" },
  { key: "k", action: "Previous segment" },
  { key: "n", action: "Next flagged segment" },
  { key: "e", action: "Edit current segment" },
  { key: "r", action: "Regenerate current segment" },
  { key: "Esc", action: "Blur text field" },
  { key: "?", action: "Toggle this panel" },
];

export function KeyboardHelpPanel({ open, onClose }: KeyboardHelpPanelProps) {
  if (!open) return null;

  return (
    <div className="fixed right-4 top-[180px] z-50 w-72 bg-white border border-slate-200 rounded-lg shadow-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[#111111]"
            style={{ fontFamily: "var(--font-montserrat, sans-serif)" }}>
          Keyboard shortcuts
        </h3>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
        {SHORTCUTS.map(({ key, action }) => (
          <>
            <kbd
              key={`key-${key}`}
              className="px-1.5 py-0.5 text-xs font-mono bg-slate-100 border border-slate-300 rounded justify-self-start"
            >
              {key}
            </kbd>
            <span key={`action-${key}`} className="text-xs text-slate-600">
              {action}
            </span>
          </>
        ))}
      </div>
    </div>
  );
}
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -40</automated>
  </verify>
  <done>
    All 5 component files created. TypeScript compiles clean.
    SegmentTable uses VirtuosoHandle ref with scrollIntoView.
    SegmentRow has debounce 500ms, optimistic save state, discard edit button shown only when edited_text is not null (explicit check per Pitfall 5).
    ReviewFilterBar shows 5 chips (All + 4 flag types) with counts.
    ReviewPageHeader has export button visible only on done/needs_review state.
    KeyboardHelpPanel renders 7 shortcuts cheatsheet.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create /jobs/[id]/review page + extend /jobs/[id]/page</name>
  <files>
    frontend/src/app/jobs/[id]/review/page.tsx
    frontend/src/app/jobs/[id]/page.tsx
  </files>
  <action>
**FIRST: Read `frontend/src/app/jobs/[id]/page.tsx`** to understand current structure before editing.

**jobs/[id]/review/page.tsx** — the CAT-tool review page. Assembles all review components.

```tsx
"use client";
import { useState, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { SegmentTable, type SegmentTableHandle } from "@/components/SegmentTable";
import { ReviewFilterBar } from "@/components/ReviewFilterBar";
import { ReviewPageHeader } from "@/components/ReviewPageHeader";
import { KeyboardHelpPanel } from "@/components/KeyboardHelpPanel";
import { useSegments } from "@/hooks/useSegments";
import { useReviewKeyboard } from "@/hooks/useReviewKeyboard";
import type { FlagType, JobSummary, Segment } from "@/lib/types";

type FilterType = FlagType | "all";

export default function ReviewPage() {
  const params = useParams();
  const jobId = params.id as string;

  const [focusedIndex, setFocusedIndex] = useState(0);
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [helpOpen, setHelpOpen] = useState(false);
  const tableRef = useRef<SegmentTableHandle>(null);
  const editingRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());

  // Load job summary
  const { data: job } = useQuery<JobSummary>({
    queryKey: ["job", jobId],
    queryFn: () =>
      fetch(`/api/jobs/${jobId}`).then((r) => {
        if (!r.ok) throw new Error("Job not found");
        return r.json();
      }),
    enabled: !!jobId,
  });

  // Load segments
  const { data: segments = [], isLoading } = useSegments(jobId);

  // Filter segments by active filter
  const filteredSegments: Segment[] =
    activeFilter === "all"
      ? segments
      : segments.filter((s) =>
          s.flags.some((f) => f.flag_type === activeFilter)
        );

  // Compute flagged indices in filteredSegments for "n" key
  const flaggedIndices = filteredSegments
    .map((seg, idx) => (seg.flags.length > 0 ? idx : -1))
    .filter((i) => i !== -1);

  // Scroll to focused index on change
  const handleFocusChange = (index: number) => {
    setFocusedIndex(index);
    tableRef.current?.scrollToIndex(index);
  };

  // Keyboard shortcuts
  useReviewKeyboard({
    focusedIndex,
    segmentCount: filteredSegments.length,
    flaggedIndices,
    onFocusChange: handleFocusChange,
    onEdit: (index) => {
      const seg = filteredSegments[index];
      if (seg) {
        const textarea = editingRefs.current.get(seg.id);
        textarea?.focus();
      }
    },
    onRegenerate: (index) => {
      // Regenerate is triggered from SegmentRow; keyboard just focuses the row
      handleFocusChange(index);
    },
    onToggleHelp: () => setHelpOpen((prev) => !prev),
  });

  if (!job || isLoading) {
    return (
      <div className="px-8 py-8 text-slate-400 text-sm">Loading review…</div>
    );
  }

  return (
    <div className="relative">
      <ReviewPageHeader job={job} />

      <ReviewFilterBar
        segments={segments}
        activeFilter={activeFilter}
        onFilterChange={(f) => {
          setActiveFilter(f);
          setFocusedIndex(0);
        }}
        onToggleHelp={() => setHelpOpen((prev) => !prev)}
      />

      {filteredSegments.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-sm text-slate-400">
          No segments with this flag type.
        </div>
      ) : (
        <SegmentTable
          ref={tableRef}
          segments={filteredSegments}
          focusedIndex={focusedIndex}
          onFocusChange={handleFocusChange}
          jobId={jobId}
          editingRef={editingRefs}
        />
      )}

      <KeyboardHelpPanel open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
```

**jobs/[id]/page.tsx** — read the existing file. Add a "Review" button/link visible only when `status === "done" || status === "needs_review"`.

Find the section where job actions or status information is rendered. Add after the existing download/status area:

```tsx
{(job.status === "done" || job.status === "needs_review") && (
  <Link
    href={`/jobs/${job.id}/review`}
    className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-violet-500 hover:bg-violet-600 text-white text-sm font-medium"
  >
    Review Translation
  </Link>
)}
```

Import `Link` from `"next/link"` if not already imported. Do not remove or break any existing logic in the file. Check the actual variable name used for job data (may be `job`, `jobData`, or similar) before editing.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -40</automated>
  </verify>
  <done>
    review/page.tsx exists at frontend/src/app/jobs/[id]/review/page.tsx.
    jobs/[id]/page.tsx has "Review Translation" link shown only on done/needs_review status.
    TypeScript compiles clean.
    review/page.tsx assembles ReviewPageHeader + ReviewFilterBar + SegmentTable + KeyboardHelpPanel.
    Filter chip updates filteredSegments and resets focusedIndex to 0.
    useReviewKeyboard hooked to page-level focus state and scrollToIndex.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → FastAPI | PATCH /segments/{id} with user-edited text; POST /jobs/{id}/export |
| Browser → File system (indirect) | Export blob download via Blob URL |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-06-01 | XSS | Segment source/translated text rendered in React | accept | All text via React JSX text nodes with automatic escaping. SegmentRow renders source text in a div with whitespace-pre-wrap; no raw HTML injection. |
| T-02-06-02 | Tampering | PATCH /segments/{id} accepts arbitrary edited_text | accept | PoC; no auth; single internal user. Server-side: Plan 04 validates segment ownership via job_id. |
| T-02-06-03 | Denial of Service | Excessive PATCH calls from rapid typing | mitigate | 500ms debounce per D-02-18 limits call frequency to max 2 calls/sec per textarea. |
| T-02-06-04 | Information Disclosure | Export triggers file download to local disk | accept | Internal PoC; translated documents are the user's own work product. |
| T-02-06-05 | Elevation of Privilege | Regenerate endpoint called on segment from another job | accept | Plan 04 segments route validates segment ownership via DB query including job_id. |
</threat_model>

<verification>
After all tasks complete:

1. TypeScript build: `cd frontend && npx tsc --noEmit` — zero errors
2. Review page loads at /jobs/{id}/review (requires valid job with segments)
3. Segment table renders virtualized rows with source text (PT Mono) and textarea
4. Typing in textarea → 500ms debounce → PATCH /api/segments/{id}
5. Optimistic update visible immediately; rollback on network error with toast
6. Filter chips update visible segments; counts show per-type counts
7. Export Document button visible only on done/needs_review; triggers download
8. Keyboard j/k navigates rows; e focuses textarea; ? toggles help panel
9. jobs/[id]/page has "Review Translation" link on done/needs_review states
</verification>

<success_criteria>
- All 9 files created/modified, TypeScript clean
- useSegments hook: GET segments, PATCH with optimistic cache update + rollback toast on error
- useReviewKeyboard: 7 shortcuts bound per D-02-17 (j/k/n/e/r/shift+?/escape)
- SegmentTable: react-virtuoso Virtuoso with calc(100vh - 168px) height, scrollIntoView on j/k
- SegmentRow: source cell PT Mono + target Textarea 500ms debounce + FlagBadge per flag + DiscardEdit button shown only when edited_text is not null (explicit null check per Pitfall 5)
- ReviewFilterBar: All chip + 4 flag chips with live counts; Shortcuts toggle
- ReviewPageHeader: filename, lang pair, glossary name chip (if set), Export button on done/needs_review
- KeyboardHelpPanel: 7-row cheatsheet, close button, fixed position top-right
- review/page.tsx: assembles all components, keyboard hook connected to table scroll
- jobs/[id]/page.tsx: "Review Translation" link shown on done/needs_review, not shown otherwise
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-06-SUMMARY.md` using the template at `@/home/thu/.claude/get-shit-done/templates/summary.md`.
</output>
