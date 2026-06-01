"use client"
import { useState } from "react"
import Link from "next/link"
import { toast } from "@/hooks/use-toast"
import { Loader2, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { forgotPasswordApi } from "@/lib/auth"

function DecorativeRings() {
  return (
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
  )
}

function ForgotForm() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  async function handleSubmit(e?: React.FormEvent, showToast = false) {
    if (e) e.preventDefault()
    setApiError(null)
    setLoading(true)
    try {
      await forgotPasswordApi(email)
      if (showToast) {
        toast({
          title: "Email sent",
          description: "Check your inbox for the reset link.",
          duration: 3000,
        })
      } else {
        setDone(true)
      }
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white px-6">
        <div className="w-full max-w-[400px]">
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
            <img src="/icons/auth/icon-email.svg" alt="Success" style={{ width: 32, height: 32 }} />
          </div>

          <div className="text-center mb-8">
            <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-1">
              Check your email
            </h2>
            <p className="text-sm text-[#6B7280]">
              We have sent a password reset link to
            </p>
            <p className="text-sm font-semibold text-[#374151] mt-0.5">{email}</p>
          </div>

          <div className="space-y-6">
              <a
                href={`mailto:${email}`}
                className="w-full h-11 rounded-xl text-sm font-semibold text-white
                  bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors
                  shadow-sm flex items-center justify-center cursor-pointer inline-block text-center no-underline"
              >
                Open email app
              </a>
            <div className="flex items-center justify-center gap-1">
              <span className="text-sm text-[#6B7280]">Didn&apos;t receive email?</span>
              <button
                type="button"
                onClick={() => handleSubmit(undefined, true)}
                disabled={loading}
                className="text-sm font-semibold text-[#3772FF] hover:text-[#2a5dcc] transition-colors disabled:opacity-60 flex items-center gap-1"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>Click to send</>
                )}
              </button>
            </div>
            <div className="mt-6 text-center">
              <Link href="/login" className="inline-flex items-center gap-1.5 text-sm text-[#3772FF] hover:text-[#2a5dcc] font-semibold transition-colors">
                <ArrowLeft className="w-4 h-4" />
                Back to log in
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <div className="w-full max-w-[400px]">

        <div className="flex justify-center mb-8 relative">
          <DecorativeRings />
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <img src="/icons/auth/icon-key.svg" alt="Forgot password" style={{ width: 32, height: 32 }} />
          </div>
        </div>

        <div className="text-center mb-6">
          <h2 className="text-[28px] font-bold leading-tight text-[#363D49] mb-1">
            Forgot password?
          </h2>
          <p className="text-sm text-[#6B7280]">
          No worries, we’ll send you reset instructions.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-sm font-medium text-[#374151]">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setApiError(null) }}
              required
              autoComplete="email"
              onInvalid={(e) => e.preventDefault()}
              className={
                apiError
                  ? "h-12 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                  : "h-12 rounded-xl border border-[#E5E7EB] bg-[#F5F5F5] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
              }
            />
            {apiError && (
              <p className="text-xs text-red-500 mt-1.5 pl-1">{apiError}</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full h-12 rounded-xl text-sm font-semibold text-white
              bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors shadow-sm
              flex items-center justify-center gap-2"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Sending...
              </>
            ) : (
              "Reset password"
            )}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <Link href="/login" className="inline-flex items-center gap-1.5 text-sm text-[#3772FF] hover:text-[#2a5dcc] font-semibold transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to log in
          </Link>
        </div>
      </div>
    </div>
  )
}

export default function ForgotPasswordPage() {
  return <ForgotForm />
}
