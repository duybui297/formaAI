"use client";
import { Keyboard } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FlagType, Segment } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ReviewFilterType = FlagType | "all";

interface ReviewFilterBarProps {
  segments: Segment[];
  activeFilter: ReviewFilterType;
  onFilterChange: (f: ReviewFilterType) => void;
  onToggleHelp: () => void;
}

const FLAG_LABELS: Record<FlagType, string> = {
  overflow: "Overflow",
  glossary_violation: "Glossary violation",
  placeholder_mismatch: "Placeholder",
  llm_refusal: "Refusal",
  smartart: "SmartArt",
  multi_column_degraded: "Multi-col",
  // Phase 4 additions (D-04-24, D-04-31)
  figure_passthrough: "Figure",
  ocr_page_error: "OCR Error",
};

const ALL_FLAGS: FlagType[] = [
  "overflow",
  "glossary_violation",
  "placeholder_mismatch",
  "llm_refusal",
  "smartart",
  "multi_column_degraded",
  // Phase 4 additions
  "figure_passthrough",
  "ocr_page_error",
];

export function ReviewFilterBar({
  segments,
  activeFilter,
  onFilterChange,
  onToggleHelp,
}: ReviewFilterBarProps) {
  const allCount = segments.length;

  const flagCounts = ALL_FLAGS.map((flagType) => ({
    flagType,
    count: segments.filter((s) =>
      s.flags.some((f) => f.flag_type === flagType)
    ).length,
  }));

  const chipBase =
    "h-8 rounded-full text-xs px-3 border transition-colors flex-shrink-0";
  const activeClass = "bg-violet-500 text-white border-violet-500";
  const inactiveClass =
    "bg-muted text-foreground border-border hover:bg-muted";

  return (
    <div className="flex items-center gap-2 h-12 px-4 bg-card border-b border-border overflow-x-auto sticky top-[120px] z-10">
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
          className={cn(
            chipBase,
            activeFilter === flagType ? activeClass : inactiveClass
          )}
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
        className="flex items-center gap-1.5 text-xs text-muted-foreground flex-shrink-0"
        onClick={onToggleHelp}
      >
        <Keyboard className="h-3.5 w-3.5" />
        Shortcuts
      </Button>
    </div>
  );
}
