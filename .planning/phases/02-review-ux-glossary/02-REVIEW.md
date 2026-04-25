---
phase: 02-review-ux-glossary
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - frontend/src/hooks/useReviewKeyboard.ts
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/components/KeyboardHelpPanel.tsx
  - frontend/src/app/layout.tsx
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 02 Gap-Closure: Code Review Report (Wave 13 — Keyboard UX + Vietnamese Font Swap)

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4 (gap-closure plans D-02-13 keyboard UX, D-02-27/D-02-14 font swap)
**Status:** issues_found

## Summary

Wave 13 covers two gap-closure plans: D-02-13 (keyboard navigation via `useReviewKeyboard` + `KeyboardHelpPanel`) and D-02-27/D-02-14 (Vietnamese font swap — PT Mono replaced by JetBrains Mono under the preserved `--font-pt-mono` CSS variable in `layout.tsx`).

The keyboard hook is logically correct — j/k navigation, n flagged-cycle, e edit, r regenerate, Escape blur, ? / Ctrl+Shift+P panel toggle, all with appropriate `enableOnFormTags` scoping. The font swap correctly loads JetBrains Mono with the `vietnamese` subset and preserves the existing CSS variable name for backwards compatibility with `SegmentRow.tsx`.

Two warnings require attention before merge: a stale-closure risk in `e`/`r` hotkey callbacks, and a missing `aria-label` on the icon-only close button in `KeyboardHelpPanel`. Four info items cover inconsistencies and minor quality improvements.

---

## Warnings

### WR-01: Stale closure risk — `onEdit` and `onRegenerate` omitted from hotkey dep arrays

**File:** `frontend/src/hooks/useReviewKeyboard.ts:58-71`

**Issue:** The `e` and `r` hotkey bindings capture `onEdit` and `onRegenerate` from the closure but only declare `[focusedIndex]` in the dependency array:

```ts
useHotkeys(
  "e",
  () => onEdit(focusedIndex),
  { preventDefault: true },
  [focusedIndex]   // onEdit missing
);

useHotkeys(
  "r",
  () => onRegenerate(focusedIndex),
  { preventDefault: true },
  [focusedIndex]   // onRegenerate missing
);
```

`react-hotkeys-hook` uses the dep array to decide when to re-subscribe the callback. With `onEdit` and `onRegenerate` absent from the array, if the parent passes non-memoized handler functions, the hotkey will call a stale captured reference. This is latent: it does not fire today if the parent happens to use `useCallback`, but nothing in this file enforces that contract, and a future parent refactor could silently break "e" / "r".

**Fix — Option A (safest, add to deps):**
```ts
useHotkeys(
  "e",
  () => onEdit(focusedIndex),
  { preventDefault: true },
  [focusedIndex, onEdit]
);

useHotkeys(
  "r",
  () => onRegenerate(focusedIndex),
  { preventDefault: true },
  [focusedIndex, onRegenerate]
);
```

**Fix — Option B (document the contract instead):**
```ts
interface ReviewKeyboardOptions {
  // ...
  /** Must be referentially stable (useCallback) — used as hotkey closure dep */
  onEdit: (index: number) => void;
  /** Must be referentially stable (useCallback) — used as hotkey closure dep */
  onRegenerate: (index: number) => void;
}
```

Option A is preferred — it requires no contract from the caller.

---

### WR-02: Icon-only close button has no accessible label

**File:** `frontend/src/components/KeyboardHelpPanel.tsx:33-41`

**Issue:** The X button renders no text and has no `aria-label`. Screen readers announce this as an unlabeled button, giving keyboard/AT users no indication of its action.

```tsx
<Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
  <X className="h-3.5 w-3.5" />
</Button>
```

**Fix:**
```tsx
<Button
  variant="ghost"
  size="icon"
  className="h-6 w-6"
  aria-label="Close keyboard shortcuts panel"
  onClick={onClose}
>
  <X className="h-3.5 w-3.5" />
</Button>
```

---

## Info

### IN-01: `inter` font variable applied to `<body>` while other font variables are on `<html>`

**File:** `frontend/src/app/layout.tsx:46-47`

**Issue:** `roboto.variable`, `montserrat.variable`, and `jetbrainsMono.variable` are all applied to the `<html>` element, but `inter.variable` is applied only to `<body>`. The CSS variables are therefore scoped differently — `--font-inter` is not available to elements outside `<body>` (e.g., `<head>` content, `<html>`-level styles). This is functionally harmless today but is inconsistent and will confuse future maintainers.

```tsx
// Current — inconsistent placement
<html lang="en" className={`${roboto.variable} ${montserrat.variable} ${jetbrainsMono.variable}`}>
  <body className={`${inter.variable} font-sans antialiased`}>
```

**Fix — Option A (consistent, all vars on `<html>`):**
```tsx
<html lang="en" className={`${inter.variable} ${roboto.variable} ${montserrat.variable} ${jetbrainsMono.variable}`}>
  <body className="font-sans antialiased">
```

**Fix — Option B (keep on `<body>`, add explanatory comment):**
```tsx
{/* inter stays on body: used only for body text; --font-inter never needed at html level */}
<body className={`${inter.variable} font-sans antialiased`}>
```

---

### IN-02: `onToggleHelp` not in dep arrays for `?` and `ctrl+shift+p` bindings

**File:** `frontend/src/hooks/useReviewKeyboard.ts:75, 79-83`

**Issue:** Both panel-toggle bindings pass no dep array at all:

```ts
useHotkeys("?", () => onToggleHelp(), { preventDefault: true });

useHotkeys(
  "ctrl+shift+p",
  () => onToggleHelp(),
  { preventDefault: true, enableOnFormTags: ["textarea"] }
);
```

Without a dep array, `react-hotkeys-hook` subscribes once and never re-subscribes when `onToggleHelp` changes. This is safe if `onToggleHelp` is stable (e.g., `useCallback` in the parent), but the omission is inconsistent with the other bindings (which all provide dep arrays) and leaves no signal to future readers. Either add `[onToggleHelp]` as a dep array, or add a comment explaining the stable-ref assumption:

```ts
// onToggleHelp is stable from the parent (useCallback) — no dep array needed.
useHotkeys("?", () => onToggleHelp(), { preventDefault: true });
```

---

### IN-03: Stale review-cycle comment label `WR-03` in `SegmentRow.tsx`

**File:** `frontend/src/components/SegmentRow.tsx:112`

**Issue:** The inline comment references a prior review cycle's finding number:

```ts
// WR-03: mark unmounted so stale mutation callbacks are no-ops
```

This is dead documentation — the number is meaningless without the prior REVIEW.md. Replace with a semantically clear comment:

```ts
// Guard stale setState after unmount: checked in patchMutation onSuccess/onError
// before any local state updates. clearTimeout (below) handles the debounce timer;
// this ref handles in-flight fetch responses.
```

---

### IN-04: `? / Ctrl+Shift+P` shortcut label in `KeyboardHelpPanel` should use consistent capitalization

**File:** `frontend/src/components/KeyboardHelpPanel.tsx:18`

**Issue:** The SHORTCUTS array uses `"? / Ctrl+Shift+P"` as the key label. The `?` symbol is correct. `Ctrl+Shift+P` uses title-cased modifier names, which is the Windows/Linux convention. On macOS, the equivalent is `⌃⇧P`. For an internal tool this is minor, but if the panel is shown on macOS the label will be slightly misleading. A neutral label (all-caps modifiers, or a note that it refers to the non-Mac binding) avoids ambiguity:

```ts
{ key: "? / Ctrl+Shift+P", action: "Toggle this panel" },
// Consider: { key: "?", action: "Toggle this panel (also Ctrl+Shift+P)" },
```

No change required for an internal PoC — flagged as awareness only.

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
