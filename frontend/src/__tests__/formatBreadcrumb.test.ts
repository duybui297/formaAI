/**
 * TDD tests for formatBreadcrumb() helper.
 *
 * RED until plan 06 creates frontend/src/lib/formatBreadcrumb.ts.
 *
 * Requirements: D-03-07 (breadcrumb badge display), UI-SPEC § formatBreadcrumb
 */

import { describe, it, expect } from "vitest"
import { formatBreadcrumb } from "@/lib/formatBreadcrumb"

describe("formatBreadcrumb", () => {
  // PPTX body: slide.N.shape.M.tf.P.para.K — all indices 1-based on display
  it("formats PPTX body position (all 1-indexed)", () => {
    expect(formatBreadcrumb("slide.3.shape.1.tf.0.para.2")).toBe("Slide 4 / Shape 2 / ¶3")
  })

  it("formats PPTX body position with all zeros (displayed as 1)", () => {
    expect(formatBreadcrumb("slide.0.shape.0.tf.0.para.0")).toBe("Slide 1 / Shape 1 / ¶1")
  })

  // PPTX notes: slide.N.notes.para.K
  it("formats PPTX notes position", () => {
    expect(formatBreadcrumb("slide.3.notes.para.1")).toBe("Slide 4 / Notes / ¶2")
  })

  // PPTX master: master.N.shape.M.para.K — treat as PPTX
  it("formats PPTX master position", () => {
    expect(formatBreadcrumb("master.0.shape.2.para.0")).toMatch(/Master|master|Slide/i)
  })

  // PPTX SmartArt: slide.N.shape.M.smartart
  it("formats PPTX SmartArt position", () => {
    const result = formatBreadcrumb("slide.3.shape.4.smartart")
    expect(result).toBeTruthy()
    expect(typeof result).toBe("string")
  })

  // PDF 2-col: page.N.col.C.block.B
  it("formats PDF 2-col position", () => {
    expect(formatBreadcrumb("page.2.col.1.block.5")).toBe("Page 3 / Col 2 / Block 6")
  })

  it("formats PDF 2-col position with all zeros (displayed as 1)", () => {
    expect(formatBreadcrumb("page.0.col.0.block.0")).toBe("Page 1 / Col 1 / Block 1")
  })

  // PDF degraded: page.N.block.B (no col segment)
  it("formats PDF degraded position", () => {
    expect(formatBreadcrumb("page.2.block.7")).toBe("Page 3 / Block 8")
  })

  // Fallback: unknown format returns raw string
  it("returns raw string for unknown format (fallback — never throw)", () => {
    const unknown = "unknown.format.string"
    expect(formatBreadcrumb(unknown)).toBe(unknown)
  })

  it("returns raw string for empty string", () => {
    expect(formatBreadcrumb("")).toBe("")
  })
})
