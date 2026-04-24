import { renderHook, act } from "@testing-library/react"
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest"
import { useCounterAnimation } from "@/hooks/useCounterAnimation"

describe("useCounterAnimation", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("snaps to target on initial render (no animation)", () => {
    const { result } = renderHook(() => useCounterAnimation(100))
    // Initial render should snap to target value
    expect(result.current).toBe(100)
  })

  it("returns target immediately when duration=0", () => {
    const { result } = renderHook(() => useCounterAnimation(50, 0))
    expect(result.current).toBe(50)
  })

  it("returns new target immediately when duration=0 on re-render", () => {
    const { result, rerender } = renderHook(
      ({ target, duration }: { target: number; duration: number }) =>
        useCounterAnimation(target, duration),
      { initialProps: { target: 0, duration: 0 } }
    )
    expect(result.current).toBe(0)

    rerender({ target: 99, duration: 0 })
    expect(result.current).toBe(99)
  })

  it("starts at previous value and animates toward new target", () => {
    // Mock requestAnimationFrame
    let rafCallback: ((time: number) => void) | null = null
    const rafSpy = vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation((cb) => {
      rafCallback = cb
      return 1
    })
    vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {})

    const { result, rerender } = renderHook(
      ({ target }: { target: number }) => useCounterAnimation(target, 300),
      { initialProps: { target: 0 } }
    )

    expect(result.current).toBe(0)

    // Change target to 100 — should start animation
    rerender({ target: 100 })

    // At start of animation, display is still near 0
    expect(rafSpy).toHaveBeenCalled()
    expect(rafCallback).not.toBeNull()

    // Simulate RAF at t=150ms (50% progress)
    act(() => {
      rafCallback!(150)
    })
    // Should be around 50 at 50% progress
    expect(result.current).toBeGreaterThanOrEqual(40)
    expect(result.current).toBeLessThanOrEqual(60)

    // Simulate RAF at t=300ms (100% progress — done)
    act(() => {
      if (rafCallback) rafCallback(300)
    })
    expect(result.current).toBe(100)

    rafSpy.mockRestore()
  })

  it("cancels animation frame on unmount to prevent state updates", () => {
    const cancelSpy = vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {})
    vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation((cb) => {
      // Schedule but don't call immediately
      return 42
    })

    const { result, rerender, unmount } = renderHook(
      ({ target }: { target: number }) => useCounterAnimation(target, 300),
      { initialProps: { target: 0 } }
    )

    // Change target to trigger RAF
    rerender({ target: 100 })

    // Unmount should cancel
    unmount()
    expect(cancelSpy).toHaveBeenCalledWith(42)
  })
})
