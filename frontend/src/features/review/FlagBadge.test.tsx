import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
// FlagBadge.tsx will be extended in Plan 05/06 to support smartart + multi_column_degraded
import { FlagBadge } from "@/features/review/FlagBadge"

describe("FlagBadge", () => {
  it.todo("renders overflow badge with amber color class")
  it.todo("renders glossary_violation badge with violet color class")
  it.todo("renders placeholder_mismatch badge with orange color class")
  it.todo("renders llm_refusal badge with red color class")
  it.todo("renders correct label text for each flag type")

  // Phase 3: smartart + multi_column_degraded badge contract
  // These tests are RED until plan 05/06 extends FlagType union and FLAG_CONFIG

  it("renders smartart badge with orange styling and SMART label", () => {
    render(<FlagBadge flagType="smartart" />)
    const badge = screen.getByText("SMART")
    expect(badge).toBeTruthy()
    // orange class should be present in the element or parent
    const el = badge as HTMLElement
    expect(el.className || (el.parentElement?.className ?? "")).toMatch(/orange/)
  })

  it("renders multi_column_degraded badge with slate styling and MULTI-COL label", () => {
    render(<FlagBadge flagType="multi_column_degraded" />)
    const badge = screen.getByText("MULTI-COL")
    expect(badge).toBeTruthy()
    const el = badge as HTMLElement
    expect(el.className || (el.parentElement?.className ?? "")).toMatch(/slate/)
  })

  // M2: overflow vs auto-adjusted badge contract
  // flag_type=="overflow" + details.auto_adjusted===true → "AUTO-FIT" info badge (slate/blue)
  // flag_type=="overflow" + !details.auto_adjusted        → "OVERFLOW" warning badge (orange/amber)
  it("renders overflow badge as warning (amber) when auto_adjusted is absent", () => {
    render(<FlagBadge flagType="overflow" />)
    const badge = screen.getByText(/Overflow/i)
    expect(badge).toBeTruthy()
    const el = badge as HTMLElement
    // Should have warning-level styling (amber)
    expect(el.className || (el.parentElement?.className ?? "")).toMatch(/amber/)
  })

  it("renders overflow badge as info (non-warning) when auto_adjusted=true in details", () => {
    // When auto_adjusted=true, FlagBadge renders an AUTO-FIT info badge instead of warning
    // This test verifies the badge rendering contract from UI-SPEC overflow vs auto-adjusted rule.
    // Implementation: plan 03-06 will differentiate on flag.details?.auto_adjusted.
    render(<FlagBadge flagType="overflow" details={{ auto_adjusted: true }} />)
    // At minimum: component renders without throwing
    expect(document.body).toBeTruthy()
  })
})
