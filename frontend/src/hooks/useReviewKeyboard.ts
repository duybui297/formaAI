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

  // ?: toggle help panel — fires when NOT inside a form element
  // Shift+/ sends event.key==="?" in all browsers (no explicit Shift modifier needed)
  useHotkeys("?", () => onToggleHelp(), { preventDefault: true });

  // ctrl+shift+p: same action — vscode-style binding that works FROM textarea
  // Additive alongside "?" (per D-02-17: locked shortcuts preserved)
  useHotkeys(
    "ctrl+shift+p",
    () => onToggleHelp(),
    { preventDefault: true, enableOnFormTags: ["textarea"] }
  );

  // Escape: blur active textarea — use setTimeout(0) for cross-browser reliability
  useHotkeys(
    "escape",
    () => {
      const el = document.activeElement as HTMLTextAreaElement | null;
      if (el && typeof el.blur === "function") {
        setTimeout(() => el.blur(), 0);
      }
    },
    { enableOnFormTags: ["textarea"] }
  );
}
