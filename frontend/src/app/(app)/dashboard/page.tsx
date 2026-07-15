"use client"
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
  Hash,
  Sparkles,
  ArrowRight,
} from "lucide-react"
import { getDashboardSummary, getNotifications } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Notification, DashboardSummary } from "@/lib/types"

// ============================================================================
// KPI Tile Components
// ============================================================================

function KpiTileSkeleton() {
  return (
    <div className="bg-card p-6 rounded-xl border border-border shadow-sm flex items-center gap-4 animate-pulse">
      <div className="w-12 h-12 rounded-lg bg-muted" />
      <div className="space-y-2 flex-1">
        <div className="h-4 w-24 bg-muted rounded" />
        <div className="h-8 w-16 bg-muted rounded" />
      </div>
    </div>
  )
}

function KpiTile({
  label,
  value,
  icon: Icon,
  color,
  bg,
  empty,
}: {
  label: string
  value: string | number | null
  icon: React.ElementType
  color: string
  bg: string
  empty?: string
}) {
  const displayValue = value ?? empty ?? "—"

  return (
    <div className="bg-card p-6 rounded-xl border border-border shadow-sm flex items-center gap-4">
      <div className={`p-3 rounded-lg ${bg} ${color}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold text-foreground">{displayValue}</p>
      </div>
    </div>
  )
}

// ============================================================================
// Notifications
// ============================================================================

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
          : "text-primary"

  return (
    <div className="flex gap-3 items-start">
      <Icon className={`w-5 h-5 mt-0.5 ${iconColor}`} />
      <div>
        <p className="text-sm font-medium text-foreground">{notif.title}</p>
        <p className="text-sm text-muted-foreground">{notif.description}</p>
        {notif.time && <p className="text-xs text-muted-foreground mt-1">{notif.time}</p>}
      </div>
    </div>
  )
}

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—"
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return n.toLocaleString()
}

// ============================================================================
// Main Dashboard Page
// ============================================================================

export default function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
    staleTime: 60 * 1000, // 60s matching backend cache TTL
  })

  const { data: notifData, isLoading: notifLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: getNotifications,
  })

  const notifications = notifData?.notifications ?? []
  const isLoading = summaryLoading || notifLoading

  // Derive display values from summary
  const stats = {
    filesTranslated: summary?.files_translated ?? 0,
    wordsProcessed: summary?.words_processed ?? 0,
    creditsRemaining: summary?.credits_remaining,
    activePlan: summary?.active_plan ?? null,
  }

  const planDisplay =
    !stats.activePlan
      ? "No Plan"
      : stats.activePlan === "ENTERPRISE"
        ? "Enterprise"
        : stats.activePlan === "PRO"
          ? "Pro"
          : stats.activePlan === "TRIAL"
            ? "Free"
            : stats.activePlan

  // Empty state: new user with no activity
  const isEmptyState = !summaryLoading && stats.filesTranslated === 0 && !stats.activePlan

  return (
    <div className="space-y-6 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Welcome back! Here&apos;s an overview of your translation activity.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/translator"
              className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:bg-primary/90 transition"
            >
              <UploadCloud className="w-4 h-4" />
              Quick Upload
            </Link>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-12 gap-3 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading dashboard…</span>
          </div>
        )}

        {/* Content */}
        {!isLoading && (
          <>
            {/* KPI Tiles */}
            {isEmptyState ? (
              /* Empty State for new users */
              <div className="bg-card p-12 rounded-xl border border-border shadow-sm text-center">
                <div className="max-w-md mx-auto space-y-4">
                  <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                    <Sparkles className="w-8 h-8 text-primary" />
                  </div>
                  <h2 className="text-xl font-semibold text-foreground">Welcome to AI Translation</h2>
                  <p className="text-muted-foreground">
                    Translate your first document to see your usage metrics here.
                  </p>
                  <Link
                    href="/translator"
                    className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-6 py-3 rounded-lg font-medium hover:bg-primary/90 transition mt-4"
                  >
                    <UploadCloud className="w-5 h-5" />
                    Translate your first file
                  </Link>
                </div>
              </div>
            ) : (
              /* KPI Tiles Grid */
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiTile
                  label="Files Translated"
                  value={formatNumber(stats.filesTranslated)}
                  icon={FileText}
                  color="text-primary"
                  bg="bg-primary/10"
                />
                <KpiTile
                  label="Words Processed"
                  value={formatNumber(stats.wordsProcessed)}
                  icon={Hash}
                  color="text-blue-600"
                  bg="bg-blue-50"
                />
                <KpiTile
                  label="Credits Remaining"
                  value={stats.creditsRemaining != null ? formatNumber(stats.creditsRemaining) : null}
                  icon={CreditCard}
                  color="text-amber-600"
                  bg="bg-amber-50"
                  empty="Unlimited"
                />
                <KpiTile
                  label="Active Plan"
                  value={planDisplay}
                  icon={CheckCircle2}
                  color="text-purple-600"
                  bg="bg-purple-50"
                />
              </div>
            )}

            {/* Bottom Section: Notifications + Pro Tip */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Notifications */}
              <div className="lg:col-span-2 bg-card p-6 rounded-xl border border-border shadow-sm">
                <h2 className="text-lg font-semibold text-foreground mb-6 flex items-center gap-2">
                  <Bell className="w-5 h-5 text-primary" />
                  Notifications
                </h2>
                {notifLoading ? (
                  <div className="space-y-3">
                    {[1, 2].map((i) => (
                      <div key={i} className="h-12 bg-muted rounded animate-pulse" />
                    ))}
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
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
              <div className="bg-primary text-primary-foreground p-5 rounded-xl border border-primary/80 shadow-sm relative overflow-hidden">
                <div className="relative z-10 flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    <h2 className="text-sm font-semibold uppercase tracking-wider">
                      Pro Tip
                    </h2>
                  </div>
                  <p className="text-primary-foreground/85 text-sm leading-snug">
                    Upload custom glossaries to keep technical terms translated
                    exactly how you want them.
                  </p>
                  <Link
                    href="/glossaries"
                    className="inline-flex items-center gap-1.5 text-sm font-medium bg-card/20 hover:bg-card/30 transition px-3 py-1.5 rounded-md self-start"
                  >
                    Manage Glossaries
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
                <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-card/10 rounded-full blur-2xl" />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
