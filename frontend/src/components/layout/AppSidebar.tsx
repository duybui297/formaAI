"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import {
  LayoutDashboard,
  FileText,
  History,
  BookA,
  Settings,
  CreditCard,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { name: "Translator", path: "/translator", icon: FileText },
  { name: "History", path: "/history", icon: History },
  { name: "Glossaries", path: "/glossaries", icon: BookA },
  { name: "Subscription", path: "/pricing", icon: CreditCard },
  { name: "Settings", path: "/settings", icon: Settings },
]

function DashScopeHealthDot() {
  const { status } = useQuery({
    queryKey: ["health"],
    queryFn: () => fetch("/api/health").then((r) => r.json()),
    refetchInterval: 30_000,
    retry: 1,
  })

  const dotColor =
    status === "success"
      ? "bg-emerald-500"
      : status === "error"
        ? "bg-red-500"
        : "bg-amber-500"

  const label =
    status === "success"
      ? "API: reachable"
      : status === "error"
        ? "API: unreachable"
        : "API: checking..."

  return (
    <div className="flex items-center gap-2" title={label}>
      <div className={`h-2 w-2 rounded-full ${dotColor}`} aria-label={label} />
      <span className="text-xs text-zinc-500">{label}</span>
    </div>
  )
}

export function AppSidebar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="flex h-screen bg-zinc-50 overflow-hidden font-sans">
      {/* Desktop Sidebar */}
      <aside className="w-64 bg-white border-r border-zinc-200 hidden md:flex flex-col flex-shrink-0">
        <div className="h-16 flex items-center px-6 border-b border-zinc-200">
          <Link href="/translator" className="flex items-center gap-2 group">
            <div className="bg-indigo-600 p-1.5 rounded-lg text-white group-hover:bg-indigo-700 transition">
              <Sparkles className="w-5 h-5" />
            </div>
            <span className="font-bold text-xl tracking-tight text-zinc-900">
              DocuTrans AI
            </span>
          </Link>
        </div>

        <div className="flex-1 overflow-y-auto py-6 px-4 space-y-1">
          {navItems.map((item) => {
            const isActive =
              pathname === item.path ||
              (item.path !== "/" && pathname?.startsWith(item.path))
            return (
              <Link
                key={item.path}
                href={item.path}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                )}
              >
                <item.icon
                  className={cn(
                    "w-5 h-5",
                    isActive ? "text-indigo-600" : "text-zinc-400"
                  )}
                />
                {item.name}
              </Link>
            )
          })}
        </div>

        <div className="p-4 border-t border-zinc-200 space-y-4">
          <DashScopeHealthDot />
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <header className="h-14 bg-white border-b border-zinc-200 flex items-center justify-between px-4 md:hidden shrink-0">
          <Link href="/translator" className="flex items-center gap-2">
            <div className="bg-indigo-600 p-1.5 rounded-lg text-white">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-bold text-lg text-zinc-900">DocuTrans AI</span>
          </Link>
          <nav className="flex items-center gap-4">
            {navItems.map((item) => (
              <Link
                key={item.path}
                href={item.path}
                className={cn(
                  "text-sm",
                  pathname?.startsWith(item.path)
                    ? "text-indigo-600 font-medium"
                    : "text-zinc-600"
                )}
              >
                {item.name}
              </Link>
            ))}
          </nav>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  )
}
