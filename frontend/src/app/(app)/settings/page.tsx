"use client"

import { useRef, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  User,
  Building,
  Key,
  Bell,
  Languages,
  ShieldCheck,
  CreditCard,
  Loader2,
  Eye,
  EyeOff,
} from "lucide-react"
import {
  updateMe,
  changePassword,
  getMyEntitlements,
  getMyLicenses,
  getNotificationPreferences,
  updateNotificationPreferences,
  getTranslationDefaults,
  updateTranslationDefaults,
  getLanguages,
  getGlossaries,
  listApiKeys,
  createApiKey,
  revokeApiKey,
  getWorkspace,
  inviteMember,
  revokeInvite,
  removeMember,
  uploadAvatar,
} from "@/lib/api"
import type {
  NotificationPreferences,
  TranslationDefaults,
  ApiKeyInfo,
  ApiKeyCreated,
  WorkspaceMember,
  WorkspaceInvite,
} from "@/lib/api"
import type { Language, Glossary } from "@/lib/types"
import { getMeApi } from "@/lib/auth"
import { useToast } from "@/hooks/use-toast"
import type { AuthUser } from "@/lib/auth"
import type { Entitlement, MyLicensesResponse } from "@/lib/types"

// ---------------------------------------------------------------------------
// Nav items
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "workspace", label: "Team Workspace", icon: Building },
  { id: "api", label: "API Keys", icon: Key },
  { id: "translation", label: "Translation Defaults", icon: Languages },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "security", label: "Security", icon: ShieldCheck },
] as const

type NavId = (typeof NAV_ITEMS)[number]["id"]

// ---------------------------------------------------------------------------
// Avatar initials helper
// ---------------------------------------------------------------------------

function getInitials(name: string | null | undefined): string {
  if (!name) return "?"
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}

// ---------------------------------------------------------------------------
// Profile tab
// ---------------------------------------------------------------------------

function ProfileTab({ user }: { user: AuthUser }) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const avatarInputRef = useRef<HTMLInputElement>(null)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(user.avatar_url ?? null)
  const [firstName, setFirstName] = useState(() => {
    const parts = (user.full_name ?? "").split(" ")
    return parts[0] ?? ""
  })
  const [lastName, setLastName] = useState(() => {
    const parts = (user.full_name ?? "").split(" ")
    return parts.slice(1).join(" ") ?? ""
  })

  const fullName = [firstName, lastName].filter(Boolean).join(" ")

  const avatarMutation = useMutation({
    mutationFn: (file: File) => uploadAvatar(file),
    onSuccess: (data) => {
      setAvatarUrl(data.avatar_url)
      queryClient.invalidateQueries({ queryKey: ["auth-user"] })
      toast({ variant: "success", title: "Avatar updated" })
    },
    onError: (err: Error) => {
      toast({ variant: "destructive", title: "Upload failed", description: err.message })
    },
  })

  const mutation = useMutation({
    mutationFn: (body: { full_name: string }) => updateMe(body),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["auth-user"] })
      toast({ variant: "success", title: "Profile saved", description: "Your changes have been saved." })
    },
    onError: (err: Error) => {
      toast({
        variant: "destructive",
        title: "Failed to save",
        description: err.message,
      })
    },
  })

  function handleSave() {
    mutation.mutate({ full_name: fullName || "" })
  }

  const hasChanges =
    fullName !== (user.full_name ?? "") ||
    firstName !== (user.full_name ?? "").split(" ")[0] ||
    lastName !== (user.full_name ?? "").split(" ").slice(1).join(" ")

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
      <div className="p-6 border-b border-zinc-200">
        <h2 className="text-lg font-semibold text-zinc-900">Personal Information</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Update your basic profile information and email.
        </p>
      </div>

      <div>
        <div className="p-6 space-y-6">
          {/* Avatar */}
          <div className="flex items-center gap-6">
            {/* Avatar display */}
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt="Avatar"
                className="w-20 h-20 rounded-full object-cover border-4 border-white shadow-sm ring-1 ring-zinc-200"
              />
            ) : (
              <div className="w-20 h-20 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-2xl font-bold border-4 border-white shadow-sm ring-1 ring-zinc-200 select-none">
                {getInitials(user.full_name)}
              </div>
            )}
            <div>
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/jpeg,image/png,image/gif,image/webp"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) {
                    if (file.size > 2 * 1024 * 1024) {
                      toast({ variant: "destructive", title: "File too large", description: "Maximum size is 2 MB." })
                      return
                    }
                    avatarMutation.mutate(file)
                  }
                  // Reset so same file can be selected again
                  e.target.value = ""
                }}
              />
              <button
                type="button"
                onClick={() => avatarInputRef.current?.click()}
                disabled={avatarMutation.isPending}
                className="bg-white border border-zinc-200 px-4 py-2 rounded-lg text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition shadow-sm cursor-pointer disabled:opacity-50"
              >
                {avatarMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading…
                  </span>
                ) : (
                  "Change Avatar"
                )}
              </button>
              <p className="text-xs text-zinc-500 mt-2">JPG, PNG, GIF or WebP. Max 2MB.</p>
            </div>
          </div>

          {/* Name fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-700" htmlFor="first-name">
                First Name
              </label>
              <input
                id="first-name"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-700" htmlFor="last-name">
                Last Name
              </label>
              <input
                id="last-name"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium text-zinc-700" htmlFor="email">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                defaultValue={user.email}
                disabled
                className="w-full bg-zinc-50 border border-zinc-300 rounded-lg px-3 py-2 text-zinc-500 cursor-not-allowed"
              />
              <p className="text-xs text-zinc-400">Email cannot be changed.</p>
            </div>
          </div>
        </div>

        <div className="p-4 bg-zinc-50 border-t border-zinc-200 flex justify-end rounded-b-xl gap-3">
          <button
            type="button"
            onClick={() => {
              const parts = (user.full_name ?? "").split(" ")
              setFirstName(parts[0] ?? "")
              setLastName(parts.slice(1).join(" ") ?? "")
            }}
            className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={mutation.isPending}
            className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm disabled:opacity-60 disabled:cursor-not-allowed transition flex items-center gap-2"
          >
            {mutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Security tab
// ---------------------------------------------------------------------------

function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [saving, setSaving] = useState(false)
  const { toast } = useToast()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (newPassword.length < 8) {
      toast({ variant: "destructive", title: "Error", description: "New password must be at least 8 characters." })
      return
    }
    if (newPassword !== confirmPassword) {
      toast({ variant: "destructive", title: "Error", description: "New passwords do not match." })
      return
    }
    if (currentPassword === newPassword) {
      toast({ variant: "destructive", title: "Error", description: "New password must be different from current password." })
      return
    }

    setSaving(true)
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword })
      toast({ variant: "success", title: "Password changed", description: "Your password has been updated." })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (err) {
      toast({ variant: "destructive", title: "Failed to change password", description: (err as Error).message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
      <div className="p-6 border-b border-zinc-200">
        <h2 className="text-lg font-semibold text-zinc-900">Change Password</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Use a strong password that you don&apos;t use elsewhere.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="p-6 space-y-5">
          {/* Current password */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="current-password">
              Current Password
            </label>
            <div className="relative">
              <input
                id="current-password"
                type={showCurrent ? "text" : "password"}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
              />
              <button
                type="button"
                onClick={() => setShowCurrent((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 transition"
              >
                {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* New password */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="new-password">
              New Password
            </label>
            <div className="relative">
              <input
                id="new-password"
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
              />
              <button
                type="button"
                onClick={() => setShowNew((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 transition"
              >
                {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-zinc-400">Minimum 8 characters.</p>
          </div>

          {/* Confirm new password */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="confirm-password">
              Confirm New Password
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
            />
          </div>
        </div>

        <div className="p-4 bg-zinc-50 border-t border-zinc-200 flex justify-end rounded-b-xl gap-3">
          <button
            type="button"
            onClick={() => {
              setCurrentPassword("")
              setNewPassword("")
              setConfirmPassword("")
            }}
            className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm disabled:opacity-60 disabled:cursor-not-allowed transition flex items-center gap-2"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            Update Password
          </button>
        </div>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Billing tab — read-only view from license + entitlement APIs
// ---------------------------------------------------------------------------

const TIER_CONFIG: Record<string, { label: string; color: string; bg: string; badge: string }> = {
  TRIAL:     { label: "Starter",    color: "text-zinc-700", bg: "bg-zinc-100",    badge: "bg-zinc-200 text-zinc-700" },
  PRO:       { label: "Professional", color: "text-indigo-700", bg: "bg-indigo-50", badge: "bg-indigo-100 text-indigo-700" },
  ENTERPRISE:{ label: "Enterprise",  color: "text-violet-700", bg: "bg-violet-50",  badge: "bg-violet-100 text-violet-700" },
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
}

function BillingTab() {
  const { data: entitlement } = useQuery({
    queryKey: ["billing-entitlement"],
    queryFn: getMyEntitlements,
  })
  const { data: licensesData } = useQuery<MyLicensesResponse>({
    queryKey: ["my-licenses"],
    queryFn: getMyLicenses,
  })

  const licenses = licensesData?.licenses ?? []
  const activeLicense = licenses.find((l) => l.status === "active") ?? licenses[0]
  const tier = entitlement?.tier ?? null
  const cfg = tier ? TIER_CONFIG[tier] : TIER_CONFIG["TRIAL"]
  const quotaUsed = entitlement?.quota_used ?? 0
  const quotaMax = entitlement?.monthly_quota ?? 0
  const quotaPct = quotaMax > 0 ? Math.min(100, Math.round((quotaUsed / quotaMax) * 100)) : 0

  return (
    <div className="space-y-4">
      {/* Current plan card */}
      <div className={`rounded-xl border p-6 ${cfg.bg} border-transparent`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-sm font-semibold ${cfg.color}`}>
                Forma
              </span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cfg.badge}`}>
                {tier ? cfg.label : "No active plan"}
              </span>
            </div>
            {activeLicense ? (
              <p className="text-sm text-zinc-500">
                License expires {formatDate(activeLicense.expired_at)}
              </p>
            ) : (
              <p className="text-sm text-zinc-500">
                No active license. Contact your administrator.
              </p>
            )}
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs text-zinc-400">Max file size</p>
            <p className="text-sm font-medium text-zinc-700">
              {entitlement?.max_file_bytes ? formatBytes(entitlement.max_file_bytes) : "—"}
            </p>
          </div>
        </div>

        {/* Feature pills */}
        <div className="flex flex-wrap gap-2 mt-4">
          {[
            { label: "DOCX / PDF / PPTX", on: true },
            { label: "OCR", on: entitlement?.ocr_allowed ?? false },
            { label: "Glossaries", on: entitlement?.glossary_allowed ?? false },
          ].map(({ label, on }) => (
            <span
              key={label}
              className={`text-xs px-2 py-1 rounded-full border ${
                on
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-zinc-200 bg-zinc-50 text-zinc-400"
              }`}
            >
              {label} {on ? "✓" : "✗"}
            </span>
          ))}
        </div>
      </div>

      {/* Usage card */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">Usage this month</h2>
          <p className="text-sm text-zinc-500 mt-1">
            {formatBytes(quotaUsed)} of {quotaMax > 0 ? formatBytes(quotaMax) : "unlimited"} used
          </p>
        </div>
        <div className="p-6">
          {quotaMax > 0 ? (
            <>
              <div className="h-2.5 bg-zinc-100 rounded-full overflow-hidden mb-3">
                <div
                  className={`h-full rounded-full transition-all ${
                    quotaPct >= 90
                      ? "bg-red-500"
                      : quotaPct >= 70
                      ? "bg-amber-500"
                      : "bg-indigo-500"
                  }`}
                  style={{ width: `${quotaPct}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-zinc-400">
                <span>{quotaPct}% used</span>
                <span>{formatBytes(Math.max(0, quotaMax - quotaUsed))} remaining</span>
              </div>
            </>
          ) : (
            <p className="text-sm text-zinc-400">No usage limit in your current plan.</p>
          )}
        </div>
      </div>

      {/* Upgrade CTA */}
      {(!tier || tier === "TRIAL") && (
        <div className="bg-indigo-600 rounded-xl p-6 flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-white">Upgrade your plan</p>
            <p className="text-sm text-indigo-200 mt-0.5">
              Unlock larger files, more quota, and advanced features.
            </p>
          </div>
          <a
            href="/pricing"
            className="shrink-0 px-4 py-2 bg-white text-indigo-700 text-sm font-semibold rounded-lg hover:bg-indigo-50 transition shadow-sm"
          >
            View Plans
          </a>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Notifications tab — toggle email notification preferences
// ---------------------------------------------------------------------------

const NOTIFICATION_ITEMS = [
  {
    key: "email_job_complete",
    title: "Job completed",
    description: "Get notified when a translation job finishes successfully.",
  },
  {
    key: "email_job_failed",
    title: "Job failed",
    description: "Get notified when a translation job encounters an error.",
  },
  {
    key: "email_license_expiry",
    title: "License expiring soon",
    description: "Get reminded 7 days before your license expires.",
  },
  {
    key: "email_license_revoked",
    title: "License revoked",
    description: "Get notified if your license is revoked or suspended.",
  },
  {
    key: "email_marketing",
    title: "Product updates",
    description: "Receive news about new features and improvements.",
  },
] as const

type NotifKey = (typeof NOTIFICATION_ITEMS)[number]["key"]

function NotificationsTab() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: prefs, isLoading } = useQuery<NotificationPreferences>({
    queryKey: ["notification-prefs"],
    queryFn: getNotificationPreferences,
    staleTime: Infinity,
  })

  const mutation = useMutation({
    mutationFn: (patch: Partial<NotificationPreferences>) =>
      updateNotificationPreferences(patch),
    onMutate: async (newPrefs) => {
      await queryClient.cancelQueries({ queryKey: ["notification-prefs"] })
      const prev = queryClient.getQueryData<NotificationPreferences>(["notification-prefs"])
      queryClient.setQueryData(["notification-prefs"], (old: NotificationPreferences | undefined) =>
        old ? { ...old, ...newPrefs } : { ...newPrefs } as NotificationPreferences
      )
      return { prev }
    },
    onError: (err: Error, _vars, context) => {
      if (context?.prev) {
        queryClient.setQueryData(["notification-prefs"], context.prev)
      }
      toast({ variant: "destructive", title: "Failed to save", description: err.message })
    },
  })

  function toggle(key: NotifKey) {
    if (!prefs) return
    mutation.mutate({ [key]: !prefs[key] })
  }

  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
      <div className="p-6 border-b border-zinc-200">
        <h2 className="text-lg font-semibold text-zinc-900">Email Notifications</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Choose which emails you want to receive.
        </p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-10 gap-3 text-zinc-400">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading preferences...</span>
        </div>
      ) : (
        <div className="divide-y divide-zinc-100">
          {NOTIFICATION_ITEMS.map(({ key, title, description }) => {
            const enabled = prefs?.[key] ?? false
            const pending = mutation.variables !== undefined && mutation.isLoading
            return (
              <div
                key={key}
                className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-zinc-50 transition"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">{title}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{description}</p>
                </div>
                {/* Accessible custom switch */}
                <button
                  role="switch"
                  aria-checked={enabled}
                  aria-label={title}
                  onClick={() => toggle(key as NotifKey)}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed ${
                    enabled ? "bg-indigo-600" : "bg-zinc-200"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                      enabled ? "translate-x-4" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Translation Defaults tab
// ---------------------------------------------------------------------------

function TranslationDefaultsTab() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: defaults, isLoading: defaultsLoading } = useQuery<TranslationDefaults>({
    queryKey: ["translation-defaults"],
    queryFn: getTranslationDefaults,
    staleTime: Infinity,
  })
  const { data: languages, isLoading: languagesLoading, isError: languagesError } = useQuery<Language[]>({
    queryKey: ["languages"],
    queryFn: getLanguages,
    staleTime: 5 * 60 * 1000,
    retry: 2,
  })
  const { data: glossaries, isLoading: glossariesLoading } = useQuery<Glossary[]>({
    queryKey: ["glossaries"],
    queryFn: getGlossaries,
    staleTime: 60 * 1000,
    retry: 1,
  })

  const mutation = useMutation({
    mutationFn: (patch: Partial<TranslationDefaults>) =>
      updateTranslationDefaults(patch),
    onMutate: async (newDefaults) => {
      await queryClient.cancelQueries({ queryKey: ["translation-defaults"] })
      const prev = queryClient.getQueryData<TranslationDefaults>(["translation-defaults"])
      queryClient.setQueryData(["translation-defaults"], (old: TranslationDefaults | undefined) =>
        old ? { ...old, ...newDefaults } : { ...newDefaults } as TranslationDefaults
      )
      return { prev }
    },
    onError: (err: Error, _vars, context) => {
      if (context?.prev) {
        queryClient.setQueryData(["translation-defaults"], context.prev)
      }
      toast({ variant: "destructive", title: "Failed to save", description: err.message })
    },
    onSuccess: () => {
      toast({ variant: "success", title: "Defaults saved" })
    },
  })

  const autoDetect = defaults?.auto_detect ?? false
  const sourceLang = defaults?.preferred_source_lang ?? ""
  const targetLang = defaults?.preferred_target_lang ?? ""
  const glossaryId = defaults?.default_glossary_id ?? ""

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">Language Preferences</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Set your default languages for new translation jobs.
          </p>
        </div>
        <div className="p-6 space-y-5">
          {/* Auto-detect */}
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-zinc-900">Auto-detect source language</p>
              <p className="text-xs text-zinc-500 mt-0.5">
                Automatically detect the language of uploaded documents.
              </p>
            </div>
            <button
              role="switch"
              aria-checked={autoDetect}
              onClick={() => mutation.mutate({ auto_detect: !autoDetect })}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                autoDetect ? "bg-indigo-600" : "bg-zinc-200"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                  autoDetect ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Source language */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="source-lang">
              Default source language
              {languagesLoading && <span className="ml-2 text-xs text-zinc-400 animate-pulse">(loading...)</span>}
            </label>
            <select
              id="source-lang"
              disabled={autoDetect || languagesLoading || languagesError}
              value={sourceLang}
              onChange={(e) => mutation.mutate({ preferred_source_lang: e.target.value || null })}
              className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">— None —</option>
              {languagesError ? (
                <option value="" disabled>Failed to load languages</option>
              ) : (
                languages?.map((l) => (
                  <option key={l.code} value={l.code}>{l.name}</option>
                ))
              )}
            </select>
          </div>

          {/* Target language */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-700" htmlFor="target-lang">
              Default target language
              {languagesLoading && <span className="ml-2 text-xs text-zinc-400 animate-pulse">(loading...)</span>}
            </label>
            <select
              id="target-lang"
              disabled={languagesLoading || languagesError}
              value={targetLang}
              onChange={(e) => mutation.mutate({ preferred_target_lang: e.target.value || null })}
              className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">— None —</option>
              {languagesError ? (
                <option value="" disabled>Failed to load languages</option>
              ) : (
                languages?.map((l) => (
                  <option key={l.code} value={l.code}>{l.name}</option>
                ))
              )}
            </select>
          </div>
        </div>
      </div>

      {/* Glossary */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">Default Glossary</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Automatically apply a glossary to new translation jobs.
          </p>
        </div>
        <div className="p-6">
          <select
            disabled={glossariesLoading}
            value={glossaryId}
            onChange={(e) =>
              mutation.mutate({ default_glossary_id: e.target.value || null })
            }
            className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="">— None —</option>
            {glossariesLoading ? (
              <option value="" disabled>Loading glossaries...</option>
            ) : (
              glossaries?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name} ({g.source_lang} → {g.target_lang}, {g.term_count} terms)
                </option>
              ))
            )}
          </select>
          {!glossariesLoading && glossaries !== undefined && glossaries.length === 0 && (
            <p className="text-xs text-zinc-400 mt-2">
              No glossaries yet.{" "}
              <a href="/glossaries" className="text-indigo-600 hover:underline">
                Create one first.
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// API Keys tab — create/list/revoke personal API keys
// ---------------------------------------------------------------------------

function ApiKeysTab() {
  const { toast } = useToast()
  const qc = useQueryClient()
  const [newKeyName, setNewKeyName] = useState("")
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [pendingCreate, setPendingCreate] = useState<ApiKeyCreated | null>(null)

  const { data: keys = [], isLoading } = useQuery<ApiKeyInfo[]>({
    queryKey: ["api-keys"],
    queryFn: listApiKeys,
    staleTime: 60 * 1000,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => createApiKey(name),
    onSuccess: (data) => {
      setPendingCreate(data)
      setNewKeyName("")
      qc.invalidateQueries({ queryKey: ["api-keys"] })
      toast({ variant: "success", title: "API key created", description: "Copy and save it now — it won't be shown again." })
    },
    onError: (err: Error) => {
      toast({ variant: "destructive", title: "Failed to create key", description: err.message })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => revokeApiKey(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-keys"] })
      toast({ variant: "success", title: "API key revoked" })
    },
    onError: (err: Error) => {
      toast({ variant: "destructive", title: "Failed to revoke key", description: err.message })
    },
  })

  async function copyKey(rawKey: string) {
    await navigator.clipboard.writeText(rawKey)
    setCopiedKey(rawKey)
    setTimeout(() => setCopiedKey(null), 2000)
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
  }

  return (
    <div className="space-y-4">
      {/* New key banner — shown once after creation */}
      {pendingCreate && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-semibold text-amber-900 text-sm mb-1">Your new API key</p>
              <p className="text-xs text-amber-700 mb-3">
                Copy this key now — it will not be shown again.
              </p>
              <code className="block bg-white border border-amber-200 rounded px-3 py-2 text-sm font-mono text-zinc-800 break-all">
                {pendingCreate.raw_key}
              </code>
            </div>
            <button
              onClick={() => { copyKey(pendingCreate.raw_key); setPendingCreate(null) }}
              className="shrink-0 text-xs text-amber-700 hover:text-amber-900 font-medium px-3 py-1.5 border border-amber-300 rounded-lg hover:bg-amber-100 transition"
            >
              {copiedKey === pendingCreate.raw_key ? "Copied!" : "Copy & Dismiss"}
            </button>
          </div>
        </div>
      )}

      {/* Create new key */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">API Keys</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Manage your personal API keys for programmatic access.
          </p>
        </div>
        <div className="p-6">
          <div className="flex gap-3">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newKeyName.trim() && !createMutation.isPending)
                  createMutation.mutate(newKeyName.trim())
              }}
              placeholder="e.g. Production, Development, CI/CD"
              maxLength={255}
              className="flex-1 bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
            />
            <button
              type="button"
              onClick={() => newKeyName.trim() && createMutation.mutate(newKeyName.trim())}
              disabled={!newKeyName.trim() || createMutation.isPending}
              className="shrink-0 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Generate Key"
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Existing keys */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">Active Keys</h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-10 gap-3 text-zinc-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading keys...</span>
          </div>
        ) : keys.length === 0 ? (
          <div className="p-10 text-center text-sm text-zinc-400">
            No API keys yet. Generate one above.
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {keys.map((key) => (
              <div key={key.id} className="px-6 py-4 flex items-center justify-between gap-4 hover:bg-zinc-50 transition">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">{key.name}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <code className="text-xs font-mono text-zinc-500">{key.key_prefix}••••••••</code>
                    <span className="text-xs text-zinc-400">Created {formatDate(key.created_at)}</span>
                    {key.last_used_at && (
                      <span className="text-xs text-zinc-400">Last used {formatDate(key.last_used_at)}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => revokeMutation.mutate(key.id)}
                  disabled={revokeMutation.isPending}
                  className="shrink-0 text-xs text-red-600 hover:text-red-800 px-3 py-1.5 border border-red-200 rounded-lg hover:bg-red-50 transition disabled:opacity-50"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Team Workspace tab — members + invite management
// ---------------------------------------------------------------------------

function TeamWorkspaceTab() {
  const { toast } = useToast()
  const qc = useQueryClient()
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")

  const { data: workspace } = useQuery<{
    members: WorkspaceMember[]
    pending_invites: WorkspaceInvite[]
  }>({
    queryKey: ["workspace"],
    queryFn: getWorkspace,
    staleTime: 60 * 1000,
  })

  const inviteMutation = useMutation({
    mutationFn: () => inviteMember(inviteEmail.trim(), inviteRole),
    onSuccess: () => {
      setInviteEmail("")
      qc.invalidateQueries({ queryKey: ["workspace"] })
      toast({ variant: "success", title: "Invitation sent", description: `Invite sent to ${inviteEmail}` })
    },
    onError: (err: Error) => {
      toast({ variant: "destructive", title: "Failed to invite", description: err.message })
    },
  })

  const revokeInviteMutation = useMutation({
    mutationFn: (id: string) => revokeInvite(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace"] })
      toast({ variant: "success", title: "Invite revoked" })
    },
    onError: (err: Error) => {
      toast({ variant: "destructive", title: "Failed to revoke", description: err.message })
    },
  })

  const removeMemberMutation = useMutation({
    mutationFn: (id: string) => removeMember(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace"] })
      toast({ variant: "success", title: "Member removed from workspace" })
    },
    onError: (err: Error) => {
      toast({ variant: "destructive", title: "Failed to remove member", description: err.message })
    },
  })

  const members = workspace?.members ?? []
  const pending = workspace?.pending_invites ?? []
  const ownerId = members.find((m) => m.role === "owner")?.id

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
  }

  return (
    <div className="space-y-4">
      {/* Invite form */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">Invite Member</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Invite collaborators to your workspace.
          </p>
        </div>
        <div className="p-6 flex flex-col sm:flex-row gap-3">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && inviteEmail.trim() && !inviteMutation.isPending)
                inviteMutation.mutate()
            }}
            placeholder="colleague@example.com"
            className="flex-1 bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="shrink-0 bg-white border border-zinc-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
          <button
            type="button"
            onClick={() => inviteEmail.trim() && inviteMutation.mutate()}
            disabled={!inviteEmail.trim() || inviteMutation.isPending}
            className="shrink-0 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {inviteMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              "Send Invite"
            )}
          </button>
        </div>
      </div>

      {/* Pending invites */}
      {pending.length > 0 && (
        <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-zinc-200">
            <h2 className="text-lg font-semibold text-zinc-900">Pending Invites</h2>
          </div>
          <div className="divide-y divide-zinc-100">
            {pending.map((inv) => (
              <div key={inv.id} className="px-6 py-4 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-900">{inv.email}</p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-zinc-400 capitalize">{inv.role}</span>
                    <span className="text-xs text-zinc-400">Expires {formatDate(inv.expires_at)}</span>
                  </div>
                </div>
                <button
                  onClick={() => revokeInviteMutation.mutate(inv.id)}
                  disabled={revokeInviteMutation.isPending}
                  className="shrink-0 text-xs text-red-600 hover:text-red-800 px-3 py-1.5 border border-red-200 rounded-lg hover:bg-red-50 transition disabled:opacity-50"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Members list */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-zinc-200">
          <h2 className="text-lg font-semibold text-zinc-900">Members</h2>
          <p className="text-sm text-zinc-500 mt-1">
            {members.length} member{members.length !== 1 ? "s" : ""} in this workspace.
          </p>
        </div>
        <div className="divide-y divide-zinc-100">
          {members.map((member) => (
            <div key={member.id} className="px-6 py-4 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 bg-indigo-100 text-indigo-700 rounded-full flex items-center justify-center text-sm font-semibold shrink-0">
                  {(member.full_name || member.email)[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-zinc-900 truncate">
                      {member.full_name || "—"}
                    </p>
                    {member.role === "owner" && (
                      <span className="shrink-0 text-xs font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">Owner</span>
                    )}
                    {member.role === "admin" && (
                      <span className="shrink-0 text-xs font-medium px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">Admin</span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400 truncate">{member.email}</p>
                </div>
              </div>
              {member.role !== "owner" && (
                <button
                  onClick={() => removeMemberMutation.mutate(member.id)}
                  disabled={removeMemberMutation.isPending}
                  className="shrink-0 text-xs text-red-600 hover:text-red-800 px-3 py-1.5 border border-red-200 rounded-lg hover:bg-red-50 transition disabled:opacity-50"
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Placeholder tabs (nav items without full UI)
// ---------------------------------------------------------------------------

const PLACEHOLDER_MESSAGES: Record<NavId, string> = {
  workspace: "Team Workspace allows you to collaborate with your colleagues on translation projects. Invite team members and manage their access levels.",
  api: "API Keys allow programmatic access to the Forma translation API. Generate and manage your API keys here.",
  translation: "Translation Defaults let you set your preferred source language, target language, and glossary for new translation jobs.",
  notifications: "Notification preferences control which emails and in-app alerts you receive for job completions and license updates.",
  billing: "Billing information and your current plan details are managed here. View invoices and upgrade or downgrade your subscription.",
}

function PlaceholderTab({ id }: { id: NavId }) {
  const navItem = NAV_ITEMS.find((n) => n.id === id)!
  const Icon = navItem.icon
  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
      <div className="p-12 flex flex-col items-center justify-center text-center gap-3">
        <div className="w-12 h-12 bg-zinc-100 rounded-full flex items-center justify-center">
          <Icon className="w-6 h-6 text-zinc-400" />
        </div>
        <div>
          <p className="font-medium text-zinc-700">{navItem.label}</p>
          <p className="text-sm text-zinc-500 mt-1 max-w-sm">
            {PLACEHOLDER_MESSAGES[id]}
          </p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

async function fetchCurrentUser(): Promise<AuthUser> {
  return await getMeApi()
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<NavId>("profile")
  const [theme, setTheme] = useState<"light" | "dark" | "system">(() => {
    if (typeof window === "undefined") return "light"
    return (localStorage.getItem("forma-theme") as "light" | "dark" | "system") ?? "light"
  })

  const { data: user, isLoading, isError } = useQuery({
    queryKey: ["auth-user"],
    queryFn: fetchCurrentUser,
    retry: false,
  })

  return (
    <div className="space-y-6 max-w-5xl p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Settings</h1>
        <p className="text-zinc-500 mt-1">
          Manage your account preferences and translation defaults.
        </p>
      </div>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Sidebar nav */}
        <div className="w-full md:w-64 shrink-0 space-y-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === item.id
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              <item.icon
                className={`w-4 h-4 ${activeTab === item.id ? "text-zinc-900" : "text-zinc-400"}`}
              />
              {item.label}
            </button>
          ))}

          {/* Divider */}
          <div className="border-t border-zinc-200 my-2" />

          {/* Theme switcher */}
          <div className="px-3 space-y-1">
            <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">Theme</p>
            <div className="flex flex-col gap-1">
              {(["light", "dark", "system"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setTheme(t)
                    localStorage.setItem("forma-theme", t)
                  }}
                  className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md text-sm transition ${
                    theme === t
                      ? "bg-indigo-50 text-indigo-700 font-medium"
                      : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800"
                  }`}
                >
                  {t === "light" && (
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
                    </svg>
                  )}
                  {t === "dark" && (
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
                    </svg>
                  )}
                  {t === "system" && (
                    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round"
                        d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
                    </svg>
                  )}
                  <span>{t.charAt(0).toUpperCase() + t.slice(1)}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 space-y-6">
          {isLoading && (
            <div className="flex items-center justify-center py-16 gap-3 text-zinc-400">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Loading settings...</span>
            </div>
          )}

          {isError && (
            <div className="bg-white rounded-xl border border-red-200 shadow-sm p-8 text-center">
              <p className="text-red-600 font-medium">Failed to load user profile.</p>
              <p className="text-sm text-zinc-500 mt-1">
                Please make sure you are{" "}
                <a href="/login" className="text-indigo-600 hover:underline">
                  logged in
                </a>
                .
              </p>
            </div>
          )}

          {user && (
            <>
              {activeTab === "profile" && <ProfileTab user={user} />}
              {activeTab === "security" && <SecurityTab />}
              {activeTab === "translation" && <TranslationDefaultsTab />}
              {activeTab === "notifications" && <NotificationsTab />}
              {activeTab === "billing" && <BillingTab />}
              {activeTab === "api" && <ApiKeysTab />}
              {activeTab === "workspace" && <TeamWorkspaceTab />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
