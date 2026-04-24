"use client";
import {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
} from "react";
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso";
import { SegmentRow } from "@/components/SegmentRow";
import type { Segment } from "@/lib/review-types";

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
  function SegmentTable(
    { segments, focusedIndex, onFocusChange, jobId, editingRef },
    ref
  ) {
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
