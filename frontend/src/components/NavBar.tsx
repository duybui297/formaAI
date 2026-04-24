"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useQuery } from "@tanstack/react-query"

function DashScopeHealthDot() {
  const { status } = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/api/health").then(r => r.json()),
    refetchInterval: 30_000,
    retry: 1,
  })

  const dotColor = status === "success" ? "bg-emerald-500"
    : status === "error" ? "bg-red-500"
    : "bg-amber-500"

  const label = status === "success" ? "API: reachable"
    : status === "error" ? "API: unreachable"
    : "API: checking..."

  return (
    <div className="flex items-center gap-2" title={label}>
      <div className={`h-2 w-2 rounded-full ${dotColor}`} aria-label={label} />
    </div>
  )
}

export function NavBar() {
  const pathname = usePathname()
  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center px-8">
      <div className="max-w-3xl mx-auto w-full flex items-center justify-between">
        <span className="text-[28px] font-semibold leading-none">AI Translation</span>
        <nav className="flex items-center gap-6">
          <Link
            href="/upload"
            className={`text-sm ${pathname === "/upload" ? "text-indigo-600 font-medium" : "text-slate-600 hover:text-slate-900"}`}
          >
            Upload
          </Link>
          <Link
            href="/jobs"
            className={`text-sm ${pathname?.startsWith("/jobs") ? "text-indigo-600 font-medium" : "text-slate-600 hover:text-slate-900"}`}
          >
            Jobs
          </Link>
          <Link
            href="/glossaries"
            className={`text-sm ${pathname?.startsWith("/glossaries") ? "text-indigo-600 font-medium" : "text-slate-600 hover:text-slate-900"}`}
          >
            Glossaries
          </Link>
          <DashScopeHealthDot />
        </nav>
      </div>
    </header>
  )
}
