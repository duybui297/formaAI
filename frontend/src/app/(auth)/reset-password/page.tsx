"use client"
import { Suspense, useState } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import Image from "next/image"
import { Eye, EyeOff, Loader2, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { resetPasswordApi } from "@/lib/auth"

function DecorativeRings() {
  return (
    <div className="flex justify-center mb-6 relative">
      <div
        aria-hidden="true"
        className="absolute select-none"
        style={{
          pointerEvents: "none",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {[0, 1, 2, 3, 4].map((i) => {
          const size = 90 + i * 52
          const opacity = 0.32 - i * 0.055
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                width: size,
                height: size,
                borderRadius: "50%",
                border: "1.5px solid rgb(202 210 227)",
                opacity: Math.max(opacity, 0.01),
              }}
            />
          )
        })}
      </div>
      <img src="/icons/auth/icon-lock.svg" alt="Lock" style={{ width: 32, height: 32, objectFit: "contain" }} />
    </div>
  )
}

function MobileLogo() {
  return (
    <div className="flex lg:hidden items-center gap-2 mb-10">
      <div className="relative w-9 h-9 shrink-0">
        <Image src="/assets/brand/logo.png" alt="Forma" fill className="object-contain" />
      </div>
      <span className="font-bold text-xl text-[#0C1B33]">Forma</span>
    </div>
  )
}

function ResetPasswordForm() {
  const searchParams = useSearchParams()
  const token = searchParams.get("token") || ""
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const passwordLengthOk = password.length >= 8
  const passwordSpecialOk = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)

  if (!token) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white px-6 lg:px-20">
        <div className="w-full max-w-[360px]">
          <MobileLogo />
          <Alert variant="destructive" className="mb-5">
            <AlertDescription>
              Missing reset token. Please request a new password reset link.
            </AlertDescription>
          </Alert>
          <div className="space-y-3">
            <Link href="/forgot-password">
              <Button variant="outline" className="w-full h-11 rounded-xl text-sm font-semibold border-[#E5E7EB] text-[#374151] hover:bg-[#F9FAFB]">
                Request new reset link
              </Button>
            </Link>
            <p className="text-center text-sm text-[#6B7280]">
              <Link href="/login" className="text-[#3772FF] hover:text-[#2a5dcc] font-semibold transition-colors">
                Back to sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setApiError(null)
    if (password !== confirmPassword) {
      setApiError("Passwords do not match")
      return
    }
    if (!passwordLengthOk || !passwordSpecialOk) {
      setApiError("Password does not meet the requirements below")
      return
    }
    setLoading(true)
    try {
      await resetPasswordApi(token, password)
      setDone(true)
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Reset failed")
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white px-6 lg:px-20">
        <div className="w-full max-w-[360px]">
          <MobileLogo />

          <div className="flex justify-center mb-6 relative">
            <div
              aria-hidden="true"
              className="absolute select-none"
              style={{
                pointerEvents: "none",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {[0, 1, 2, 3, 4].map((i) => {
                const size = 90 + i * 52
                const opacity = 0.32 - i * 0.055
                return (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      width: size,
                      height: size,
                      borderRadius: "50%",
                      border: "1.5px solid rgb(202 210 227)",
                      opacity: Math.max(opacity, 0.01),
                    }}
                  />
                )
              })}
            </div>
            <img src="/icons/auth/icon-check.svg" alt="Success" style={{ width: 52, height: 52, objectFit: "contain" }} />
          </div>

          <div className="text-center mb-9">
            <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-1">
              Reset Password Successfully
            </h2>
            <p className="text-sm text-[#6B7280]">
              Your new password has been successfully reset!
            </p>
          </div>

          <Link href="/login">
            <Button className="w-full h-11 rounded-xl text-sm font-semibold text-white bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors shadow-sm">
              Login
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex items-center justify-center bg-white px-6 lg:px-20">
      <div className="w-full max-w-[360px]">
        <MobileLogo />

        <DecorativeRings />

        <div className="text-center mb-6">
          <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-1">
            Set new password
          </h2>
          <p className="text-sm text-[#6B7280]">
            Your new password must be different to previously used password
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-sm font-medium text-[#374151]">
              New password
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setApiError(null) }}
                required
                autoComplete="new-password"
                className={
                  apiError
                    ? "h-11 pr-10 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                    : "h-11 pr-10 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
                }
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280] transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            {apiError && (
              <p className="text-xs text-red-500 mt-1.5 pl-1">{apiError}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="confirmPassword" className="text-sm font-medium text-[#374151]">
              Confirm new password
            </Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showPassword ? "text" : "password"}
                placeholder="Repeat new password"
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); setApiError(null) }}
                required
                autoComplete="new-password"
                className={
                  apiError
                    ? "h-11 pr-10 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                    : "h-11 pr-10 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
                }
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280] transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Password rules */}
            <div className="space-y-1 pt-1">
              <div className="flex items-center gap-2">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${passwordLengthOk ? "bg-green-500" : "bg-[#E5E7EB]"}`}>
                  {passwordLengthOk && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={3} />}
                </div>
                <span className={`text-xs ${passwordLengthOk ? "text-green-600" : "text-[#9CA3AF]"}`}>
                  Must be at least 8 characters
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${passwordSpecialOk ? "bg-green-500" : "bg-[#E5E7EB]"}`}>
                  {passwordSpecialOk && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={3} />}
                </div>
                <span className={`text-xs ${passwordSpecialOk ? "text-green-600" : "text-[#9CA3AF]"}`}>
                  Must contain one special character
                </span>
              </div>
            </div>

          <Button
            type="submit"
            className="w-full h-11 rounded-xl text-sm font-semibold text-white
              bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors shadow-sm mt-1"
            disabled={loading}
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" />Resetting...</>
            ) : (
              "Reset password"
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <Suspense
        fallback={
          <div className="flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-[#3772FF]" />
          </div>
        }
      >
        <ResetPasswordForm />
      </Suspense>
    </div>
  )
}
