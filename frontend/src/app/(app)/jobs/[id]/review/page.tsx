"use client";
import { use, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { KeyboardHelpPanel } from "@/features/review/KeyboardHelpPanel";
import { ReviewFilterBar, type ReviewFilterType } from "@/features/review/ReviewFilterBar";
import { ReviewPageHeader } from "@/features/review/ReviewPageHeader";
import {
  SegmentTable,
  type SegmentTableHandle,
} from "@/features/review/SegmentTable";
import { useSegments } from "@/hooks/useSegments";
import { useReviewKeyboard } from "@/hooks/useReviewKeyboard";
import { useToast } from "@/hooks/use-toast";
import { authFetch } from "@/lib/auth";
import type { JobSummary, Segment } from "@/lib/types";

// Next.js 16 async params: unwrap with React.use() per D-20
export default function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: jobId } = use(params);
  const { toast } = useToast();

  const [focusedIndex, setFocusedIndex] = useState(0);
  const [activeFilter, setActiveFilter] = useState<ReviewFilterType>("all");
  const [helpOpen, setHelpOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const tableRef = useRef<SegmentTableHandle>(null);
  const editingRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());

  // Load job summary for header (extended with low_confidence_pages — D-04-14)
  const { data: job } = useQuery<JobSummary>({
    queryKey: ["job", jobId],
    queryFn: () =>
      authFetch(`/v1/jobs/${jobId}`).then((r) => {
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

  // Phase 4: D-04-22 — Download menu handler
  const handleDownload = async (artifact: "bilingual_pdf" | "translated_pdf" | "translated_docx") => {
    if (!job) return;
    setDownloading(true);
    try {
      const res = await authFetch(`/v1/jobs/${jobId}/artifacts?artifact=${artifact}`, {
        method: "GET",
      });
      if (!res.ok) {
        toast({ title: "Download failed. Try again.", variant: "destructive" });
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const extMatch = job.original_filename.match(/\.[^./\\]+$/);
      const ext = extMatch ? extMatch[0] : ".docx";
      a.download = job.original_filename.replace(/(\.\w+)?$/, `_translated${ext}`);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 100);
    } catch {
      toast({ title: "Network error — download could not be initiated.", variant: "destructive" });
    } finally {
      setDownloading(false);
    }
  };

  const canDownload = ["done", "needs_review"].includes(job?.status ?? "");

  if (!job || isLoading) {
    return (
      <>
        <div className="px-8 py-8 text-muted-foreground text-sm">
          Loading review…
        </div>
      </>
    );
  }

  return (
    <>
      <div className="relative">
        <ReviewPageHeader job={job} />

        {/* Phase 4: D-04-14 — Low-confidence banner */}
        {job.low_confidence_pages && job.low_confidence_pages.length > 0 && (
          <div className="flex items-start gap-3 mx-8 mb-4 mt-4 px-4 py-3 rounded-md border border-amber-300 bg-amber-50">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-amber-800">
              <strong className="text-amber-900">Low OCR confidence:</strong>{" "}
              Pages{" "}
              {job.low_confidence_pages.map((n, i) => (
                <span key={n}>
                  <button
                    type="button"
                    className="font-semibold underline cursor-pointer text-amber-900 hover:text-amber-700"
                    onClick={() => {
                      const idx =
                        filteredSegments.findIndex((s) =>
                          s.structural_position?.startsWith(`page.${n}.`)
                        ) ?? -1;
                      if (idx >= 0 && tableRef.current) {
                        tableRef.current.scrollToIndex(idx);
                      }
                    }}
                  >
                    {n + 1}
                  </button>
                  {i < (job.low_confidence_pages?.length ?? 0) - 1 ? ", " : ""}
                </span>
              ))}{" "}
              have low OCR confidence — verify before export.
            </p>
          </div>
        )}

        {/* Phase 4: D-04-22 — Download dropdown menu */}
        {canDownload && (
          <div className="flex justify-end px-8 mb-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={downloading}
                >
                  Download <ChevronDown className="ml-1 h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => handleDownload("bilingual_pdf")}>
                  Bilingual PDF
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleDownload("translated_pdf")}>
                  Translated PDF
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleDownload("translated_docx")}>
                  Translated DOCX
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}

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
          <div className="flex items-center justify-center h-32 text-sm text-muted-foreground">
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
