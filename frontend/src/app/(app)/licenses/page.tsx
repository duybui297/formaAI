"use client"

import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import {
  Key,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Ban,
  Loader2,
  RefreshCw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { getMyLicenses } from "@/lib/api"
import type { MyLicenseItem, MyLicensesResponse, LicenseTier, LicenseStatus } from "@/lib/types"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TIER_LABELS: Record<LicenseTier, string> = {
  starter: "Starter",
  professional: "Professional",
  enterprise: "Enterprise",
}

const STATUS_CONFIG: Record<
  LicenseStatus,
  { label: string; icon: React.ElementType; color: string; bg: string }
> = {
  pending: {
    label: "Pending Activation",
    icon: Clock,
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-200",
  },
  active: {
    label: "Active",
    icon: CheckCircle2,
    color: "text-emerald-600",
    bg: "bg-emerald-50 border-emerald-200",
  },
  expired: {
    label: "Expired",
    icon: XCircle,
    color: "text-red-600",
    bg: "bg-red-50 border-red-200",
  },
  suspended: {
    label: "Suspended",
    icon: AlertTriangle,
    color: "text-orange-600",
    bg: "bg-orange-50 border-orange-200",
  },
  revoked: {
    label: "Revoked",
    icon: Ban,
    color: "text-muted-foreground",
    bg: "bg-muted border-input",
  },
}

function formatDate(iso: string | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function LicenseCard({ license }: { license: MyLicenseItem }) {
  const cfg = STATUS_CONFIG[license.status]
  const StatusIcon = cfg.icon
  const isPending = license.status === "pending"

  return (
    <div
      className={`rounded-xl border p-5 space-y-4 ${cfg.bg}`}
      data-status={license.status}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-white border border-current/20 rounded-lg p-2">
            <Key className={`w-4 h-4 ${cfg.color}`} />
          </div>
          <div>
            <p className="font-semibold text-foreground">
              {TIER_LABELS[license.tier] ?? license.tier}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              License #{license.id.slice(0, 8)}
            </p>
          </div>
        </div>

        <div className={`flex items-center gap-1.5 text-sm font-medium ${cfg.color}`}>
          <StatusIcon className="w-4 h-4" />
          {cfg.label}
        </div>
      </div>

      {/* Meta */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground text-xs">Issued</p>
          <p className="font-medium text-foreground">{formatDate(license.issued_at)}</p>
        </div>
        <div>
          <p className="text-muted-foreground text-xs">Activated</p>
          <p className="font-medium text-foreground">{formatDate(license.activated_at)}</p>
        </div>
        <div>
          <p className="text-muted-foreground text-xs">Expires</p>
          <p className="font-medium text-foreground">{formatDate(license.expired_at)}</p>
        </div>
      </div>

      {/* Pending CTA */}
      {isPending && (
        <div className="pt-2 border-t border-amber-200/60">
          <p className="text-sm text-amber-700 mb-3">
            This license is waiting to be activated. Enter your license key to get started.
          </p>
          <Button
            asChild
            className="bg-amber-600 hover:bg-amber-700 text-white text-sm"
          >
            <a href="/activate">
              <Key className="w-4 h-4 mr-2" />
              Activate Now
            </a>
          </Button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MyLicensesPage() {
  const router = useRouter()

  const { data, isLoading, isError, refetch, isFetching } = useQuery<MyLicensesResponse>({
    queryKey: ["my-licenses"],
    queryFn: getMyLicenses,
    refetchOnWindowFocus: true,
  })

  const licenses = data?.licenses ?? []
  const pendingCount = data?.pending_count ?? 0
  const activeCount = licenses.filter((l) => l.status === "active").length

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-5 border-b border-border bg-card flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold font-montserrat text-foreground">
            My Licenses
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            View and manage your assigned licenses.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {pendingCount > 0 && (
            <div className="flex items-center gap-1.5 text-sm font-medium text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-lg">
              <Clock className="w-4 h-4" />
              {pendingCount} pending activation
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && (
          <div className="flex items-center justify-center py-16 gap-3 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading your licenses...</span>
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center py-16 gap-4">
            <p className="text-muted-foreground">Failed to load licenses.</p>
            <Button variant="outline" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Try again
            </Button>
          </div>
        )}

        {!isLoading && !isError && licenses.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
            <div className="bg-muted rounded-full p-4">
              <Key className="w-8 h-8 text-muted-foreground" />
            </div>
            <div>
              <p className="font-semibold text-foreground">No licenses yet</p>
              <p className="text-sm text-muted-foreground mt-1 max-w-xs">
                Contact your administrator to get a license assigned to your account.
              </p>
            </div>
          </div>
        )}

        {!isLoading && !isError && licenses.length > 0 && (
          <div className="space-y-4 max-w-2xl">
            {/* Summary strip */}
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>
                <strong className="text-foreground">{licenses.length}</strong> total license
                {licenses.length !== 1 ? "s" : ""}
              </span>
              {activeCount > 0 && (
                <span>
                  <strong className="text-emerald-600">{activeCount}</strong> active
                </span>
              )}
              {pendingCount > 0 && (
                <span>
                  <strong className="text-amber-600">{pendingCount}</strong> pending
                </span>
              )}
            </div>

            {/* License cards */}
            <div className="space-y-3">
              {licenses.map((lic) => (
                <LicenseCard key={lic.id} license={lic} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
