"use client"

import { useState } from "react"
import { Loader2, CheckCircle2, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { activateLicense } from "@/lib/api"
import type { ActivateLicenseResponse, ActivateErrorCode } from "@/lib/types"

// ---------------------------------------------------------------------------
// Key auto-format helpers
// ---------------------------------------------------------------------------

/** Strip non-alphanumeric and uppercase, then insert hyphens every 4 chars */
function formatKey(raw: string): string {
  const clean = raw.replace(/[^a-zA-Z0-9]/g, "").toUpperCase()
  const groups: string[] = []
  for (let i = 0; i < clean.length && groups.length < 4; i += 4) {
    groups.push(clean.slice(i, i + 4))
  }
  return groups.join("-")
}

// ---------------------------------------------------------------------------
// Error display config
// ---------------------------------------------------------------------------

interface ErrorConfig {
  variant: "red" | "amber"
  message: string
  showRenewal: boolean
}

const ERROR_CONFIGS: Record<ActivateErrorCode, ErrorConfig> = {
  INVALID_KEY: {
    variant: "red",
    message: "Invalid license key. Please check your key and try again.",
    showRenewal: false,
  },
  ALREADY_ACTIVATED: {
    variant: "amber",
    message: "This license key has already been activated on another device.",
    showRenewal: false,
  },
  EXPIRED: {
    variant: "red",
    message: "This license key has expired.",
    showRenewal: true,
  },
}

// ---------------------------------------------------------------------------
// ActivateForm
// ---------------------------------------------------------------------------

export function ActivateForm() {
  const [rawKey, setRawKey] = useState("")
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState<ActivateLicenseResponse | null>(null)
  const [errorCode, setErrorCode] = useState<ActivateErrorCode | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  function handleKeyChange(e: React.ChangeEvent<HTMLInputElement>) {
    const formatted = formatKey(e.target.value)
    setRawKey(formatted)
    // Clear previous error when user edits
    setErrorCode(null)
    setErrorMessage(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!rawKey.trim()) return

    setLoading(true)
    setSuccess(null)
    setErrorCode(null)
    setErrorMessage(null)

    try {
      const result = await activateLicense(rawKey)
      if (result.ok) {
        setSuccess(result.data)
        // Persist activation data for the expiry banner
        if (typeof window !== "undefined") {
          localStorage.setItem("forma_license", JSON.stringify(result.data))
        }
      } else {
        setErrorCode(result.error.code)
        setErrorMessage(result.error.message)
      }
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return <SuccessCard data={success} />
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="activate-form"
      className="space-y-6"
    >
      <div className="space-y-1.5">
        <Label
          htmlFor="license-key"
          className="text-sm font-medium text-[#374151]"
        >
          License Key
        </Label>
        <Input
          id="license-key"
          data-testid="license-key-input"
          type="text"
          placeholder="XXXX-XXXX-XXXX-XXXX"
          value={rawKey}
          onChange={handleKeyChange}
          maxLength={19} // 4×4 chars + 3 hyphens
          autoComplete="off"
          spellCheck={false}
          className="h-11 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm font-mono text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors uppercase tracking-wider"
        />
      </div>

      {errorCode && (
        <ErrorAlert code={errorCode} serverMessage={errorMessage} />
      )}

      <Button
        type="submit"
        data-testid="activate-submit"
        className="w-full h-11 rounded-xl text-sm font-semibold text-white bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors shadow-sm"
        disabled={loading || rawKey.length < 4}
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            Activating...
          </>
        ) : (
          "Activate License"
        )}
      </Button>
    </form>
  )
}

// ---------------------------------------------------------------------------
// ErrorAlert
// ---------------------------------------------------------------------------

function ErrorAlert({
  code,
  serverMessage,
}: {
  code: ActivateErrorCode
  serverMessage: string | null
}) {
  const cfg = ERROR_CONFIGS[code]
  const message = serverMessage ?? cfg.message

  const colorClasses =
    cfg.variant === "red"
      ? "bg-red-50 border-red-200 text-red-800"
      : "bg-amber-50 border-amber-200 text-amber-800"

  return (
    <div
      role="alert"
      data-testid="activate-error"
      data-variant={cfg.variant}
      data-code={code}
      className={`rounded-lg border px-4 py-3 text-sm ${colorClasses}`}
    >
      <p>{message}</p>
      {cfg.showRenewal && (
        <a
          href="/pricing"
          data-testid="renewal-link"
          className="mt-1 inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:opacity-80"
        >
          Renew your license
          <ExternalLink className="w-3 h-3" />
        </a>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// SuccessCard
// ---------------------------------------------------------------------------

function SuccessCard({ data }: { data: ActivateLicenseResponse }) {
  const expiryDisplay = data.expiry
    ? new Date(data.expiry).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "No expiry"

  const tierLabel =
    data.tier.charAt(0).toUpperCase() + data.tier.slice(1)

  return (
    <div
      role="status"
      data-testid="activate-success"
      className="rounded-xl border border-green-200 bg-green-50 px-6 py-5 space-y-4"
    >
      <div className="flex items-center gap-2 text-green-700">
        <CheckCircle2 className="w-5 h-5" />
        <span className="font-semibold text-base">License activated!</span>
      </div>

      <dl className="space-y-2 text-sm text-[#374151]">
        <div className="flex gap-2">
          <dt className="font-medium w-20 shrink-0">Tier</dt>
          <dd data-testid="success-tier">{tierLabel}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="font-medium w-20 shrink-0">Expires</dt>
          <dd data-testid="success-expiry">{expiryDisplay}</dd>
        </div>
        {data.features.length > 0 && (
          <div className="flex gap-2">
            <dt className="font-medium w-20 shrink-0 pt-0.5">Features</dt>
            <dd data-testid="success-features">
              <ul className="space-y-0.5">
                {data.features.map((f) => (
                  <li key={f} className="text-green-700">
                    {f}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>
    </div>
  )
}
