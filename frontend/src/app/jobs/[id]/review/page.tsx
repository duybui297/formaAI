"use client";
import { use, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavBar } from "@/components/NavBar";
import { KeyboardHelpPanel } from "@/components/KeyboardHelpPanel";
import { ReviewFilterBar, type ReviewFilterType } from "@/components/ReviewFilterBar";
import { ReviewPageHeader } from "@/components/ReviewPageHeader";
import {
  SegmentTable,
  type SegmentTableHandle,
} from "@/components/SegmentTable";
import { useSegments } from "@/hooks/useSegments";
import { useReviewKeyboard } from "@/hooks/useReviewKeyboard";
import type { JobSummary } from "@/lib/types";
import type { Segment } from "@/lib/review-types";

// Next.js 16 async params: unwrap with React.use() per D-20
export default function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: jobId } = use(params);

  const [focusedIndex, setFocusedIndex] = useState(0);
  const [activeFilter, setActiveFilter] = useState<ReviewFilterType>("all");
  const [helpOpen, setHelpOpen] = useState(false);
  const tableRef = useRef<SegmentTableHandle>(null);
  const editingRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());

  // Load job summary for header
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

  // Filter segments by active flag type
  const filteredSegments: Segment[] =
    activeFilter === "all"
      ? segments
      : segments.filter((s) =>
          s.flags.some((f) => f.flag_type === activeFilter)
        );

  // Compute flagged indices in filteredSegments for the "n" shortcut
  const flaggedIndices = filteredSegments
    .map((seg, idx) => (seg.flags.length > 0 ? idx : -1))
    .filter((i) => i !== -1);

  const handleFocusChange = (index: number) => {
    setFocusedIndex(index);
    tableRef.current?.scrollToIndex(index);
  };

  // Bind all keyboard shortcuts
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
      // Keyboard "r" focuses the row; SegmentRow's regenerate button handles the mutation
      handleFocusChange(index);
    },
    onToggleHelp: () => setHelpOpen((prev) => !prev),
  });

  if (!job || isLoading) {
    return (
      <>
        <NavBar />
        <div className="px-8 py-8 text-slate-400 text-sm">
          Loading review…
        </div>
      </>
    );
  }

  return (
    <>
      <NavBar />
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
    </>
  );
}
