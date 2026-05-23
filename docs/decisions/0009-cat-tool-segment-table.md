# ADR-0009: shadcn Table review UI, not Monaco DiffEditor

**Status**: Accepted
**Date**: 2026-05-01 (Phase 2, decision D-02-14)
**Decider(s)**: Thu

## Context

The review UI needs to show source and translated segments side by side,
let reviewers edit translations inline, and handle documents with
hundreds of segments without scroll lag.

Three patterns considered:

1. **Monaco DiffEditor** — VS Code's diff editor, supports edit on the
   right pane.
2. **CAT-tool style segment table** — one row per segment, source +
   target columns, inline `<Textarea>` per row.
3. **Custom rich-text editor** — full WYSIWYG document diff.

Original PoC plan picked Monaco. Phase 2 user testing surfaced
problems.

## Decision

Use a **shadcn Table with one `<Textarea>` per row** for the review UI.
`react-virtuoso` handles variable-height virtualization for long
documents. TanStack Query v5 with optimistic mutations
(`onMutate → cancelQueries → setQueryData → onError rollback`) for the
segment PATCH endpoint.

Monaco DiffEditor stays in `package.json` (cheap to keep, eval again
post-Phase 3) but is not used for review.

## Alternatives considered

- **Monaco DiffEditor** — designed for two text blobs, not for many
  small independent segments. Treats the whole doc as one diff;
  per-segment edits are awkward; CJK text rendering quirks; no
  native virtualization for hundreds of segments.
- **Full WYSIWYG iframe preview** — requires WASM PDF renderer. Too
  much engineering for PoC scope.
- **`react-diff-viewer`** — read-only, doesn't support inline edit.

## Consequences

- ✅ Familiar pattern for translation reviewers (mirrors Trados, MemoQ).
- ✅ Virtualization handles long docs without lag.
- ✅ Each row is an independent edit with optimistic update — no
  global save dance.
- ✅ Built on shadcn primitives we already use; no new heavy dep.
- ⚠️ No document-level WYSIWYG preview during review; reviewer must
  trust the export to render correctly. Acceptable for PoC.
- ⚠️ Re-evaluate Monaco removal after Phase 3 — if still unused,
  delete to shrink bundle.

## References

- `CLAUDE.md` → *Conventions* → *CAT-tool segment table pattern*
- `frontend/src/components/SegmentTable.tsx`
- `frontend/src/components/SegmentRow.tsx`
- `.planning/phases/02-review-ux-glossary/02-06-review-frontend-PLAN.md`
