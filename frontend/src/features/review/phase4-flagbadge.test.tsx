import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { FlagBadge } from "@/features/review/FlagBadge"

describe("Phase 4 FlagBadge extensions", () => {
  it("renders figure_passthrough badge with FIGURE label", () => {
    render(<FlagBadge flagType="figure_passthrough" />)
    const badge = screen.getByText("FIGURE")
    expect(badge).toBeTruthy()
  })

  it("renders figure_passthrough badge with slate styling (info severity)", () => {
    render(<FlagBadge flagType="figure_passthrough" />)
    const badge = screen.getByText("FIGURE") as HTMLElement
    const classStr = badge.className || (badge.parentElement?.className ?? "")
    expect(classStr).toMatch(/slate/)
  })

  it("renders ocr_page_error badge with OCR ERR label", () => {
    render(<FlagBadge flagType="ocr_page_error" />)
    const badge = screen.getByText("OCR ERR")
    expect(badge).toBeTruthy()
  })

  it("renders ocr_page_error badge with amber styling (warn severity)", () => {
    render(<FlagBadge flagType="ocr_page_error" />)
    const badge = screen.getByText("OCR ERR") as HTMLElement
    const classStr = badge.className || (badge.parentElement?.className ?? "")
    expect(classStr).toMatch(/amber/)
  })
})
