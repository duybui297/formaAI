"use client"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import {
  LayoutDashboard,
  FileText,
  History,
  BookA,
  Settings,
  CreditCard,
  Sparkles,
  LogOut,
  User as UserIcon,
  ShieldCheck,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getMeApi, logoutApi } from "@/lib/auth"
import type { AuthUser } from "@/lib/auth"

const navItems = [
  { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { name: "Translator", path: "/translator", icon: FileText },
  { name: "History", path: "/history", icon: History },
  { name: "Glossaries", path: "/glossaries", icon: BookA },
  { name: "Subscription", path: "/pricing", icon: CreditCard },
  { name: "Settings", path: "/settings", icon: Settings },
]

const adminNavItems = [
  { name: "Licenses", path: "/admin/licenses", icon: ShieldCheck },
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

function UserSection() {
  const router = useRouter()
  const { data: user } = useQuery<AuthUser>({
    queryKey: ["me"],
    queryFn: getMeApi,
    retry: 1,
  })

  async function handleSignOut() {
    try {
      await logoutApi()
    } catch {
      // ignore — client-side session already cleared by logoutApi
    }
    router.push("/login")
    router.refresh()
  }

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-full bg-zinc-200 flex items-center justify-center">
          <UserIcon className="w-3.5 h-3.5 text-zinc-400" />
        </div>
        <div className="flex flex-col min-w-0">
          <Link href="/login" className="text-xs text-indigo-600 hover:underline">
            Sign in
          </Link>
          <Link href="/register" className="text-xs text-zinc-400 hover:text-zinc-600">
            Register
          </Link>
        </div>
      </div>
    )
  }

  const initials = user.full_name
    ? user.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
    : user.email[0].toUpperCase()

  return (
    <div className="flex items-center gap-2">
      <div className="h-7 w-7 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
        {initials}
      </div>
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-xs font-medium text-zinc-900 truncate">
          {user.full_name || user.email.split("@")[0]}
        </span>
        <span className="text-xs text-zinc-400 truncate">{user.email}</span>
      </div>
      <button
        onClick={handleSignOut}
        className="text-zinc-400 hover:text-red-600 transition flex-shrink-0 ml-1"
        title="Sign out"
      >
        <LogOut className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function AppSidebar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: user } = useQuery<AuthUser>({
    queryKey: ["me"],
    queryFn: getMeApi,
    retry: 1,
  })

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

          {user?.is_superuser && (
          <div className="pt-4">
            <p className="px-3 pb-1 text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Admin
            </p>
            {adminNavItems.map((item) => {
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
          )}
        </div>

        <div className="p-4 border-t border-zinc-200 space-y-4">
          <DashScopeHealthDot />
          <UserSection />
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
