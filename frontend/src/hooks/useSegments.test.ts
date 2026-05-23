import { describe, it, vi } from "vitest"
// NOTE: useSegments/useSegmentPatch will be created in Plan 06
// import { useSegmentPatch } from "@/hooks/useSegments"

describe("useSegmentPatch", () => {
  it.todo("optimistic update sets edited_text in cache immediately — D-02-19")
  it.todo("cache rollback restores previous value on PATCH error — D-02-19")
  it.todo("toast 'Could not save — edit restored.' shown on error — D-02-18")
  it.todo("cancelQueries called in onMutate before setQueryData — Pitfall 4")
})
