"use client"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { useEffect, useRef } from "react"
import type { JobProgress } from "@/lib/types"
import { getToken } from "@/lib/auth"

const TERMINAL = new Set(["done", "failed", "needs_review"])

export function useJobProgress(jobId: string) {
  const queryClient = useQueryClient()
  const sseOpen = useRef(false)

  useEffect(() => {
    const ctrl = new AbortController()
    sseOpen.current = true

    const token = getToken()
    const headers: Record<string, string> = {}
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }

    fetchEventSource(`/api/jobs/${jobId}/stream`, {
      signal: ctrl.signal,
      headers,
      onmessage(ev) {
        const data: JobProgress = JSON.parse(ev.data)
        queryClient.setQueryData(["job", jobId], data)
      },
      onerror() {
        sseOpen.current = false  // triggers polling fallback
      },
      onclose() {
        sseOpen.current = false
      },
    })

    return () => ctrl.abort()
  }, [jobId, queryClient])

  return useQuery<JobProgress>({
    queryKey: ["job", jobId],
    queryFn: () => authFetch(`/jobs/${jobId}`).then(r => r.json()),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && TERMINAL.has(status)) return false
      if (sseOpen.current) return false
      return 2000  // poll every 2s when SSE closed (D-09 fallback)
    },
    staleTime: 0,
  })
}
