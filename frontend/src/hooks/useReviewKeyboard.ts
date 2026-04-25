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
    () => {
      if (segmentCount === 0) return;
      onFocusChange(Math.min(focusedIndex + 1, segmentCount - 1));
    },
    { preventDefault: true },
    [focusedIndex, segmentCount]
  );

  // k: previous segment
  useHotkeys(
    "k",
    () => {
      if (segmentCount === 0) return;
      onFocusChange(Math.max(focusedIndex - 1, 0));
    },
    { preventDefault: true },
    [focusedIndex, segmentCount]
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
  useHotkeys(
    "e",
    () => onEdit(focusedIndex),
    { preventDefault: true },
    [focusedIndex]
  );

  // r: regenerate focused segment
  useHotkeys(
    "r",
    () => onRegenerate(focusedIndex),
    { preventDefault: true },
    [focusedIndex]
  );

  // ?: toggle help panel — detect event.key==="?" directly (Shift+/ sends "?" in all browsers)
  // Using shift+/ is wrong: it would match event.key==="/", but Shift held transforms / to ?
  useHotkeys("?", () => onToggleHelp(), { preventDefault: true });

  // Escape: blur active textarea (enabled in textarea)
  useHotkeys(
    "escape",
    () => (document.activeElement as HTMLElement)?.blur(),
    { enableOnFormTags: ["textarea"] }
  );
}
