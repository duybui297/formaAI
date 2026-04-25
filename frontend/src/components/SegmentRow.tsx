"use client";
import { useEffect, useRef, useState } from "react";
import { Check, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSegmentPatch, useSegmentRegenerate } from "@/hooks/useSegments";
import type { FlagType, Segment } from "@/lib/review-types";
import { cn } from "@/lib/utils";
import { formatBreadcrumb } from "@/lib/formatBreadcrumb";

// Inline flag badge — avoids dependency on FlagBadge.tsx (plan 05 scope)
const FLAG_BADGE_STYLES: Record<FlagType, string> = {
  overflow: "bg-amber-100 text-amber-800 border-amber-300",
  glossary_violation: "bg-violet-100 text-violet-800 border-violet-300",
  placeholder_mismatch: "bg-orange-100 text-orange-800 border-orange-300",
  llm_refusal: "bg-red-100 text-red-800 border-red-300",
  smartart: "bg-orange-100 text-orange-800 border-orange-300",
  multi_column_degraded: "bg-slate-100 text-slate-600 border-slate-300",
};

const FLAG_LABELS: Record<FlagType, string> = {
  overflow: "Overflow",
  glossary_violation: "Glossary",
  placeholder_mismatch: "Placeholder",
  llm_refusal: "Refusal",
  smartart: "SMART",
  multi_column_degraded: "MULTI-COL",
};

function InlineFlagBadge({ flagType }: { flagType: FlagType }) {
  return (
    <span
      className={cn(
        "inline-block text-[10px] px-1.5 py-0.5 rounded border leading-tight",
        FLAG_BADGE_STYLES[flagType]
      )}
    >
      {FLAG_LABELS[flagType]}
    </span>
  );
}

const LEFT_BORDER: Record<FlagType, string> = {
  overflow: "border-l-amber-500",
  glossary_violation: "border-l-violet-500",
  placeholder_mismatch: "border-l-orange-500",
  llm_refusal: "border-l-red-500",
  smartart: "border-l-orange-500",
  multi_column_degraded: "border-l-slate-400",
};

interface SegmentRowProps {
  segment: Segment;
  isFocused: boolean;
  jobId: string;
  onFocus: () => void;
  textareaRef?: (el: HTMLTextAreaElement | null) => void;
}

export function SegmentRow({
  segment,
  isFocused,
  jobId,
  onFocus,
  textareaRef,
}: SegmentRowProps) {
  // Display value: edited_text > translated_text > ""
  const displayValue =
    segment.edited_text !== null
      ? segment.edited_text
      : (segment.translated_text ?? "");

  const [localValue, setLocalValue] = useState(displayValue);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">(
    "idle"
  );
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const isMountedRef = useRef(true);

  const patchMutation = useSegmentPatch(jobId);
  const regenerateMutation = useSegmentRegenerate(jobId);

  // Sync local value when segment data changes externally (e.g. regenerate)
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
            if (!isMountedRef.current) return;
            setSaveState("saved");
            savedTimerRef.current = setTimeout(() => {
              if (isMountedRef.current) setSaveState("idle");
            }, 1500);
          },
          // CRITICAL: reset saveState on error — UI must not stay stuck on "Saving…"
          // Hook-level onError handles cache rollback + toast; this resets local UI state.
          onError: () => {
            if (!isMountedRef.current) return;
            setSaveState("idle");
          },
        }
      );
    }, 500);
  };

  // WR-03: mark unmounted so stale mutation callbacks are no-ops
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Cleanup debounce and saved-state timers on unmount
  useEffect(() => {
    return () => {
      clearTimeout(debounceRef.current);
      clearTimeout(savedTimerRef.current);
    };
  }, []);

  const primaryFlag =
    segment.flags.length > 0 ? segment.flags[0].flag_type : null;

  return (
    <div
      data-focused={isFocused ? "true" : undefined}
      className={cn(
        "flex border-b border-slate-100 border-l-4",
        isFocused ? "ring-2 ring-violet-500 bg-violet-50" : "",
        primaryFlag
          ? (LEFT_BORDER[primaryFlag] ?? "border-l-transparent")
          : "border-l-transparent",
        "hover:bg-slate-50 cursor-pointer"
      )}
      onClick={onFocus}
    >
      {/* Sequence index */}
      <div className="w-12 flex-shrink-0 py-2 px-1 text-xs text-slate-400 select-none">
        {segment.seq_in_job}
      </div>

      {/* Source cell: monospace, read-only */}
      <div
        className="flex-[40] py-2 px-2 text-xs font-mono text-[#111111] bg-slate-50 border-r border-slate-100 select-text min-h-[48px] whitespace-pre-wrap"
        style={{ fontFamily: "var(--font-pt-mono, monospace)" }}
      >
        {segment.structural_position && (
          <span className="text-xs text-slate-400 font-mono mb-1 block select-none">
            {formatBreadcrumb(segment.structural_position)}
          </span>
        )}
        {segment.source_text}
      </div>

      {/* Target cell: editable textarea with debounce */}
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

        {/* Save state indicator + regenerate button row */}
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-slate-400">
            {saveState === "saving" && "Saving…"}
            {saveState === "saved" && (
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3" /> Saved
              </span>
            )}
          </span>
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

        {/* Discard edit: only shown when edited_text is explicitly non-null */}
        {segment.edited_text !== null && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-red-500 hover:text-red-700 h-6 px-1 self-start"
            onClick={(e) => {
              e.stopPropagation();
              patchMutation.mutate({
                segmentId: segment.id,
                editedText: null,
              });
            }}
          >
            Discard edit
          </Button>
        )}
      </div>

      {/* Flag cell */}
      <div className="w-20 flex-shrink-0 py-2 px-1 flex flex-col gap-1">
        {segment.flags.map((flag) => (
          <InlineFlagBadge key={flag.id} flagType={flag.flag_type} />
        ))}
      </div>
    </div>
  );
}
