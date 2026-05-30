"use client"
import { Suspense, useState, useEffect, useCallback } from "react"
import Link from "next/link"
import Image from "next/image"
import { useRouter, useSearchParams } from "next/navigation"
import { Eye, EyeOff, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { loginApi, setToken, setStoredUser, setAuthCookie } from "@/lib/auth"

const AUTH_COOKIE = "forma_access_token"
const COOKIE_MAX_AGE = 60 * 60 * 8

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [rememberMe, setRememberMe] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  // Redirect param set by middleware when unauthenticated user hits a protected page
  const redirectTo = searchParams.get("redirect") || "/dashboard"

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setApiError(null)
    setLoading(true)
    try {
      const result = await loginApi({ email, password })
      setToken(result.access_token)
      // Set httpOnly-accessible cookie so middleware can read it (Edge Runtime)
      setAuthCookie(result.access_token)
      const meRes = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${result.access_token}` },
      })
      if (meRes.ok) {
        const user = await meRes.json()
        setStoredUser(user)
      }
      router.push(redirectTo)
      router.refresh()
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex relative">
      <div className="hidden lg:flex lg:w-[50%] relative overflow-hidden">
        <div
          aria-hidden="true"
          className="absolute select-none"
          style={{ pointerEvents: "none", top: 0, left: 0, width: "100%", height: "100%" }}
        >
          <Image src="/assets/images/login-poster.png" alt="" fill className="object-cover" />
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center bg-white px-6 lg:px-20">
        <div className="w-full max-w-[360px]">

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
            <img
              src="/assets/brand/logo.png"
              alt="Forma"
              style={{ width: 52, height: 52, objectFit: "contain" }}
            />
          </div>

          <div className="text-center mb-6">
            <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-1">
              Login to Forma
              
            </h2>
            <p className="text-sm text-[#6B7280]">
              Welcome back! Please enter your details.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email */}
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
                    ? "h-11 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                    : "h-11 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
                }
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium text-[#374151]">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setApiError(null) }}
                  required
                  autoComplete="current-password"
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
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              {apiError && (
                <p className="text-xs text-red-500 mt-1.5 pl-1">{apiError}</p>
              )}
            </div>

            {/* Remember me + Forgot password */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <Checkbox
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                <span className="text-sm text-[#6B7280]">Remember me</span>
              </label>
              <Link
                href="/forgot-password"
                className="text-sm text-[#3772FF] hover:text-[#2a5dcc] font-medium transition-colors"
              >
                Forgot password
              </Link>
            </div>

            {/* Submit */}
            <Button
              type="submit"
              className="w-full h-11 rounded-xl text-sm font-semibold text-white
                bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors
                shadow-sm mt-1"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </Button>
          </form>
          {/* Register link */}
          <p className="mt-6 text-center text-sm text-[#6B7280]">
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="text-[#3772FF] hover:text-[#2a5dcc] font-semibold transition-colors"
            >
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-white">
          <Loader2 className="w-6 h-6 animate-spin text-[#3772FF]" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
