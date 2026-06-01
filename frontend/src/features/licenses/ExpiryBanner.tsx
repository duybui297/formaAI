"use client"

import { useState, useEffect } from "react"
import { X, ExternalLink, AlertTriangle } from "lucide-react"
import type { ActivateLicenseResponse } from "@/lib/types"

const STORAGE_KEY_LICENSE = "forma_license"
const STORAGE_KEY_DISMISSED = "forma_expiry_banner_dismissed"

/**
 * Days remaining until the given ISO date string.
 * Returns null if expiry is null (no expiry = no banner needed).
 */
function daysUntil(isoDate: string | null): number | null {
  if (!isoDate) return null
  const expiry = new Date(isoDate).getTime()
  const now = Date.now()
  const diff = expiry - now
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

// ---------------------------------------------------------------------------
// ExpiryBanner
// ---------------------------------------------------------------------------

/**
 * Global expiry warning banner.
 *
 * - Reads license from localStorage ("forma_license").
 * - Shows when expiry < 7 days (including negative = already expired).
 * - EXPIRED (days <= 0) shows a renewal link.
 * - Dismiss persists via localStorage ("forma_expiry_banner_dismissed"),
 *   keyed to the expiry date so a new license clears the dismissed state.
 */
export function ExpiryBanner() {
  const [license, setLicense] = useState<ActivateLicenseResponse | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Load license
    try {
      const raw = localStorage.getItem(STORAGE_KEY_LICENSE)
      if (raw) {
        const parsed: ActivateLicenseResponse = JSON.parse(raw)
        setLicense(parsed)
      }
    } catch {
      // corrupt storage — ignore
    }

    // Load dismissed state
    try {
      const dismissedKey = localStorage.getItem(STORAGE_KEY_DISMISSED)
      if (dismissedKey) {
        setDismissed(true)
      }
    } catch {
      // ignore
    }
  }, [])

  if (!mounted || !license) return null

  const days = daysUntil(license.expiry)

  // Only show when < 7 days remaining (or already expired)
  if (days === null || days >= 7) return null
  if (dismissed) return null

  const isExpired = days <= 0

  function handleDismiss() {
    setDismissed(true)
    try {
      // Store dismiss keyed to expiry so a renewed license shows again
      localStorage.setItem(
        STORAGE_KEY_DISMISSED,
        license?.expiry ?? "no-expiry"
      )
    } catch {
      // ignore
    }
  }

  const bgClasses = isExpired
    ? "bg-red-50 border-red-200 text-red-800"
    : "bg-amber-50 border-amber-200 text-amber-800"

  const message = isExpired
    ? "Your license has expired."
    : days === 1
    ? "Your license expires tomorrow."
    : `Your license expires in ${days} days.`

  return (
    <div
      role="alert"
      data-testid="expiry-banner"
      data-expired={isExpired}
      data-days={days}
      className={`flex items-center gap-3 border-b px-4 py-2.5 text-sm ${bgClasses}`}
    >
      <AlertTriangle className="w-4 h-4 shrink-0" />

      <span className="flex-1">
        {message}
        {isExpired && (
          <a
            href="/pricing"
            data-testid="banner-renewal-link"
            className="ml-2 inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:opacity-80"
          >
            Renew now
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </span>

      <button
        type="button"
        data-testid="expiry-banner-dismiss"
        aria-label="Dismiss expiry warning"
        onClick={handleDismiss}
        className="shrink-0 rounded-md p-0.5 hover:bg-black/10 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
