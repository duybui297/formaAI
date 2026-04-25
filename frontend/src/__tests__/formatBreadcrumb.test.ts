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
  // PPTX body: slide.N.shape.M.tf.P.para.K
  it("formats PPTX body position (1-indexed shape)", () => {
    // shape index 1 → displayed as Shape 2 (1-based per UI-SPEC)
    expect(formatBreadcrumb("slide.3.shape.1.tf.0.para.2")).toBe("Slide 3 / Shape 2 / ¶2")
  })

  it("formats PPTX body position with shape 0 (displayed as Shape 1)", () => {
    expect(formatBreadcrumb("slide.0.shape.0.tf.0.para.0")).toBe("Slide 0 / Shape 1 / ¶0")
  })

  // PPTX notes: slide.N.notes.para.K
  it("formats PPTX notes position", () => {
    expect(formatBreadcrumb("slide.3.notes.para.1")).toBe("Slide 3 / Notes / ¶1")
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
    expect(formatBreadcrumb("page.2.col.1.block.5")).toBe("Page 2 / Col 1 / Block 5")
  })

  it("formats PDF 2-col position col 0", () => {
    expect(formatBreadcrumb("page.0.col.0.block.0")).toBe("Page 0 / Col 0 / Block 0")
  })

  // PDF degraded: page.N.block.B (no col segment)
  it("formats PDF degraded position", () => {
    expect(formatBreadcrumb("page.2.block.7")).toBe("Page 2 / Block 7")
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
