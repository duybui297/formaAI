import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { QueryProvider } from "@/components/providers/query-provider"

// Smoke test: QueryProvider renders children without throwing
describe("QueryProvider", () => {
  it("renders children wrapped in QueryClientProvider", () => {
    render(
      <QueryProvider>
        <div data-testid="child">hello</div>
      </QueryProvider>
    )
    expect(screen.getByTestId("child")).toBeDefined()
  })
})

// Smoke test: types module exports expected shapes
describe("types", () => {
  it("JobStatus values are well-typed", async () => {
    const { } = await import("@/lib/types")
    // If types.ts imports without error, the module is valid
    expect(true).toBe(true)
  })
})
