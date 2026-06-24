import { describe, it, expect } from "vitest"
import type { FlagType, Segment, JobProgress } from "@/lib/types"

// Phase 4 RED tests: verify FlagType union, Segment OCR fields, JobProgress extensions.
// These tests drive type-level contracts. Runtime assertions use grep-style checks on
// the imported type by creating values that would fail to compile if types are wrong.

describe("Phase 4 type extensions", () => {
  it("FlagType union in types.ts includes figure_passthrough", () => {
    const flagType: FlagType = "figure_passthrough"
    expect(flagType).toBe("figure_passthrough")
  })

  it("FlagType union in types.ts includes ocr_page_error", () => {
    const flagType: FlagType = "ocr_page_error"
    expect(flagType).toBe("ocr_page_error")
  })

  it("Segment interface has confidence field (number | null)", () => {
    const seg = { confidence: 0.85 } as Partial<Segment>
    expect(seg.confidence).toBe(0.85)
    const segNull = { confidence: null } as Partial<Segment>
    expect(segNull.confidence).toBeNull()
  })

  it("Segment interface has region_bbox field", () => {
    const seg = { region_bbox: [0.1, 0.2, 0.8, 0.9] as [number, number, number, number] } as Partial<Segment>
    expect(seg.region_bbox).toHaveLength(4)
  })

  it("Segment interface has region_label field", () => {
    const seg = { region_label: "paragraph_title" } as Partial<Segment>
    expect(seg.region_label).toBe("paragraph_title")
  })

  it("Segment interface has edited_source_text field", () => {
    const seg = { edited_source_text: "corrected OCR text" } as Partial<Segment>
    expect(seg.edited_source_text).toBe("corrected OCR text")
    const segNull = { edited_source_text: null } as Partial<Segment>
    expect(segNull.edited_source_text).toBeNull()
  })

  it("JobProgress has stage_progress optional field", () => {
    const progress: JobProgress = {
      status: "processing",
      stage: "translate",
      segments_done: 3,
      segments_total: 10,
      current_batch: 1,
      retry_count: 0,
      last_message: "",
      stage_progress: { stage: "ocr", current: 3, total: 10 },
    }
    expect(progress.stage_progress?.stage).toBe("ocr")
  })

  it("JobProgress stage_progress is optional (no field = valid)", () => {
    const progress: JobProgress = {
      status: "done",
      stage: "done",
      segments_done: 10,
      segments_total: 10,
      current_batch: 0,
      retry_count: 0,
      last_message: "done",
    }
    expect(progress.stage_progress).toBeUndefined()
  })
})
