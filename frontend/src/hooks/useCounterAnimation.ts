"use client"
import { useEffect, useRef, useState } from "react"

export function useCounterAnimation(target: number, duration = 300): number {
  const [display, setDisplay] = useState(target) // snap on first render
  const rafRef = useRef<number | null>(null)
  const startRef = useRef<number | null>(null)
  const fromRef = useRef(target)

  useEffect(() => {
    if (duration === 0) {
      setDisplay(target)
      fromRef.current = target
      return
    }
    const from = fromRef.current
    if (from === target) return

    startRef.current = null

    const step = (now: number) => {
      if (startRef.current === null) startRef.current = now
      const elapsed = now - startRef.current
      const progress = Math.min(elapsed / duration, 1)
      setDisplay(Math.round(from + (target - from) * progress))
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step)
      } else {
        fromRef.current = target
        startRef.current = null
      }
    }
    rafRef.current = requestAnimationFrame(step)
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [target, duration])

  return display
}
