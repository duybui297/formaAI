"use client"
import { useMemo } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import {
  FileText,
  UploadCloud,
  TrendingUp,
  CreditCard,
  Bell,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
  AlertTriangle,
} from "lucide-react"
import { listJobs } from "@/lib/api"
import { getMyEntitlements, getNotifications } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Notification, JobSummary } from "@/lib/types"

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  if (!bytes) return "—"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
}: {
  label: string
  value: string
  icon: React.ElementType
  color: string
  bg: string
}) {
  return (
    <div className="bg-white p-6 rounded-xl border border-zinc-200 shadow-sm flex items-center gap-4">
      <div className={`p-3 rounded-lg ${bg} ${color}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-sm font-medium text-zinc-500">{label}</p>
        <p className="text-2xl font-bold text-zinc-900">{value}</p>
      </div>
    </div>
  )
}

function NotificationItem({ notif }: { notif: Notification }) {
  const Icon =
    notif.type === "job_complete"
      ? CheckCircle2
      : notif.type === "job_failed"
        ? AlertCircle
        : notif.type === "license_expiry"
          ? Clock
          : AlertTriangle

  const iconColor =
    notif.type === "job_complete"
      ? "text-emerald-500"
      : notif.type === "job_failed"
        ? "text-red-500"
        : notif.type === "license_expiry"
          ? "text-amber-500"
          : "text-indigo-500"

  return (
    <div className="flex gap-3 items-start">
      <Icon className={`w-5 h-5 mt-0.5 ${iconColor}`} />
      <div>
        <p className="text-sm font-medium text-zinc-900">{notif.title}</p>
        <p className="text-sm text-zinc-500">{notif.description}</p>
        {notif.time && <p className="text-xs text-zinc-400 mt-1">{notif.time}</p>}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs-recent"],
    queryFn: () => listJobs({ page: 1, page_size: 5 }),
  })

  const { data: entitlements, isLoading: entLoading } = useQuery({
    queryKey: ["entitlements"],
    queryFn: getMyEntitlements,
  })

  const { data: notifData, isLoading: notifLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: getNotifications,
  })

  const jobs: JobSummary[] = jobsData?.jobs ?? []

  const stats = useMemo(() => {
    const completedJobs = jobs.filter((j) => j.status === "done")
    const totalFiles = completedJobs.length

    // Approximate word count from number of completed jobs
    // (exact word count per job not currently stored; display job count as proxy)
    const wordProxy = totalFiles * 1200 // rough estimate per job for display

    const tierLabel = entitlements?.tier ?? null
    const tierDisplay =
      !entitlements || !entitlements.has_active
        ? "No Plan"
        : tierLabel === "ENTERPRISE"
          ? "Enterprise"
          : tierLabel === "PRO"
            ? "Pro"
            : tierLabel === "TRIAL"
              ? "Free"
              : tierLabel ?? "—"

    const maxBytes = entitlements?.max_file_bytes ?? 0
    const quotaRemaining =
      entitlements?.monthly_quota !== null && entitlements?.monthly_quota !== undefined
        ? Math.max(0, (entitlements.monthly_quota ?? 0) - (entitlements.quota_used ?? 0))
        : null

    return {
      totalFiles,
      wordProxy,
      quotaRemaining,
      quotaUsed: entitlements?.quota_used ?? 0,
      maxBytes,
      tierDisplay,
      hasActive: entitlements?.has_active ?? false,
    }
  }, [jobs, entitlements])

  // Build chart data from last 6 months of job history
  const chartData = useMemo(() => {
    const now = new Date()
    const months: { name: string; words: number }[] = []
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
      const monthStr = d.toLocaleString("default", { month: "short" })
      const monthStart = new Date(d.getFullYear(), d.getMonth(), 1)
      const monthEnd = new Date(d.getFullYear(), d.getMonth() + 1, 0)

      const monthJobs = jobs.filter((j) => {
        const created = new Date(j.created_at)
        return created >= monthStart && created <= monthEnd
      })
      const doneJobs = monthJobs.filter((j) => j.status === "done")
      months.push({
        name: monthStr,
        words: doneJobs.length * 1200,
      })
    }
    return months
  }, [jobs])

  const maxWords = Math.max(...chartData.map((d) => d.words), 1)
  const notifications = notifData?.notifications ?? []
  const isLoading = jobsLoading || entLoading || notifLoading

  return (
    <div className="space-y-6 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Dashboard</h1>
            <p className="text-zinc-500 mt-1">
              Welcome back! Here&apos;s an overview of your translation activity.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/translator"
              className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 transition"
            >
              <UploadCloud className="w-4 h-4" />
              Quick Upload
            </Link>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12 gap-3 text-zinc-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading dashboard…</span>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                label="Files Translated"
                value={stats.totalFiles.toLocaleString()}
                icon={FileText}
                color="text-indigo-600"
                bg="bg-indigo-50"
              />
              <StatCard
                label="Jobs This Month"
                value={String(stats.quotaUsed)}
                icon={TrendingUp}
                color="text-emerald-600"
                bg="bg-emerald-50"
              />
              <StatCard
                label="Credits Remaining"
                value={
                  stats.quotaRemaining !== null
                    ? stats.quotaRemaining.toLocaleString()
                    : "Unlimited"
                }
                icon={CreditCard}
                color="text-amber-600"
                bg="bg-amber-50"
              />
              <StatCard
                label="Active Plan"
                value={stats.tierDisplay}
                icon={CheckCircle2}
                color="text-purple-600"
                bg="bg-purple-50"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Chart */}
              <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-zinc-200 shadow-sm">
                <h2 className="text-lg font-semibold text-zinc-900 mb-6">Translation Volume</h2>
                {chartData.every((d) => d.words === 0) ? (
                  <div className="h-[300px] flex items-center justify-center">
                    <div className="text-center text-zinc-400">
                      <FileText className="w-10 h-10 mx-auto mb-2 opacity-40" />
                      <p className="text-sm">No translation data yet.</p>
                      <Link href="/translator" className="text-indigo-600 text-sm hover:underline mt-1 inline-block">
                        Upload your first document →
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="h-[300px] flex items-end gap-3 px-2">
                    {chartData.map((d) => (
                      <div key={d.name} className="flex-1 flex flex-col items-center gap-2">
                        <span className="text-xs text-zinc-500">
                          {d.words > 0 ? `${(d.words / 1000).toFixed(0)}k` : "0"}
                        </span>
                        <div
                          className="w-full bg-indigo-600 rounded-t-md transition-all"
                          style={{ height: `${Math.max(4, (d.words / maxWords) * 240)}px` }}
                        />
                        <span className="text-xs text-zinc-500">{d.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-6">
                {/* Notifications */}
                <div className="bg-white p-6 rounded-xl border border-zinc-200 shadow-sm">
                  <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
                    <Bell className="w-5 h-5 text-indigo-600" />
                    Notifications
                  </h2>
                  {notifLoading ? (
                    <div className="space-y-3">
                      {[1, 2].map((i) => (
                        <div key={i} className="h-12 bg-zinc-100 rounded animate-pulse" />
                      ))}
                    </div>
                  ) : notifications.length === 0 ? (
                    <div className="text-center text-zinc-400 py-6">
                      <Bell className="w-8 h-8 mx-auto mb-2 opacity-40" />
                      <p className="text-sm">No notifications</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {notifications.slice(0, 5).map((notif) => (
                        <NotificationItem key={notif.id} notif={notif} />
                      ))}
                    </div>
                  )}
                </div>

                {/* Pro Tip */}
                <div className="bg-indigo-600 text-white p-6 rounded-xl border border-indigo-500 shadow-sm relative overflow-hidden">
                  <div className="relative z-10">
                    <h2 className="text-lg font-semibold mb-2">Pro Tip</h2>
                    <p className="text-indigo-100 text-sm mb-4">
                      Did you know? You can upload custom glossaries to ensure technical terms are
                      always translated exactly how you want them.
                    </p>
                    <Link
                      href="/glossaries"
                      className="text-sm font-medium bg-white/20 hover:bg-white/30 transition px-3 py-1.5 rounded-md inline-block"
                    >
                      Manage Glossaries
                    </Link>
                  </div>
                  <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-white/10 rounded-full blur-2xl" />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
