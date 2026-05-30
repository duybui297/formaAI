"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { getMeApi } from "@/lib/auth"
import type { AuthUser } from "@/lib/auth"

/**
 * Admin route guard: only is_superuser users may view /admin/**.
 * Non-admins are redirected to /dashboard. Defense-in-depth on top of the
 * sidebar gating and the backend's 403 on admin APIs.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { data: user, isLoading } = useQuery<AuthUser>({
    queryKey: ["me"],
    queryFn: getMeApi,
  })

  const isAdmin = !!user?.is_superuser

  useEffect(() => {
    if (!isLoading && user && !isAdmin) {
      router.replace("/dashboard")
    }
  }, [isLoading, user, isAdmin, router])

  if (isLoading || !user) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-400">
        Loading…
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-500">
        Forbidden — redirecting…
      </div>
    )
  }

  return <>{children}</>
}
