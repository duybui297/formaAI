"use client"
import { Suspense, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Eye, EyeOff, Loader2, ArrowRight, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { signupApi } from "@/lib/auth"

function validateEmail(value: string): string | null {
  if (!value) return "Email is required"
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Please enter a valid email address"
  return null
}

function validatePassword(value: string): string | null {
  if (!value) return "Password is required"
  if (value.length < 8) return "Password must be at least 8 characters"
  if (!/[A-Z]/.test(value)) return "Password must contain at least one uppercase letter"
  if (!/\d/.test(value)) return "Password must contain at least one number"
  return null
}

function validateConfirmPassword(value: string, password: string): string | null {
  if (!value) return "Please confirm your password"
  if (value !== password) return "Passwords do not match"
  return null
}

function validateFullName(value: string): string | null {
  if (!value.trim()) return "Full name is required"
  return null
}

function SignupForm() {
  const router = useRouter()

  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const [fullNameError, setFullNameError] = useState<string | null>(null)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  function clearFullNameError() {
    setFullNameError(null)
    setApiError(null)
  }

  function clearEmailError() {
    setEmailError(null)
    setApiError(null)
  }

  function clearPasswordError() {
    setPasswordError(null)
    setApiError(null)
  }

  function clearConfirmPasswordError() {
    setConfirmPasswordError(null)
    setApiError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setApiError(null)
    setFullNameError(null)
    setEmailError(null)
    setPasswordError(null)
    setConfirmPasswordError(null)

    const fullNameValidation = validateFullName(fullName)
    if (fullNameValidation) {
      setFullNameError(fullNameValidation)
      return
    }
    const emailValidation = validateEmail(email)
    if (emailValidation) {
      setEmailError(emailValidation)
      return
    }
    const passwordValidation = validatePassword(password)
    if (passwordValidation) {
      setPasswordError(passwordValidation)
      return
    }
    const confirmValidation = validateConfirmPassword(confirmPassword, password)
    if (confirmValidation) {
      setConfirmPasswordError(confirmValidation)
      return
    }

    setLoading(true)
    try {
      await signupApi({
        email,
        password,
        full_name: fullName || undefined,
      })
      // US-1.1: do NOT auto-login — user must verify email first.
      setSuccess(true)
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Sign up failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white px-6">
        <div className="w-full max-w-[420px] text-center">
          <div className="flex justify-center mb-6">
            <CheckCircle2 className="w-16 h-16 text-[#3772FF]" />
          </div>
          <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-3">
            Check your email
          </h2>
          <p className="text-sm text-[#6B7280] mb-2">
            We&apos;ve sent a verification link to
          </p>
          <p className="text-sm font-semibold text-[#0C1B33] mb-6">
            {email}
          </p>
          <p className="text-sm text-[#6B7280] mb-8 leading-relaxed">
            Click the link in the email to activate your account.
            The link expires in <strong>24 hours</strong>.
          </p>
          <Button
            type="button"
            onClick={() => router.push("/login")}
            className="w-full h-11 rounded-xl text-sm font-semibold text-white
              bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors shadow-sm"
          >
            Back to sign in
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <div className="w-full max-w-[360px]">

        {/* Logo decoration */}
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

        {/* Heading */}
        <div className="text-center mb-6">
          <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-1">
            Create your account
          </h2>
          <p className="text-sm text-[#6B7280]">
            Start translating documents today
          </p>
        </div>

        {apiError && (
          <p className="text-xs text-red-500 mb-4 pl-1">{apiError}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Full name */}
          <div className="space-y-1.5">
            <Label htmlFor="full_name" className="text-sm font-medium text-[#374151]">
              Full name
            </Label>
            <Input
              id="full_name"
              type="text"
              placeholder="Enter your full name"
              value={fullName}
              onChange={(e) => { setFullName(e.target.value); clearFullNameError() }}
              autoComplete="name"
              className={
                fullNameError
                  ? "h-11 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                  : "h-11 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
              }
            />
            {fullNameError && (
              <p className="text-xs text-red-500 mt-1.5 pl-1">{fullNameError}</p>
            )}
          </div>

          {/* Email */}
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-sm font-medium text-[#374151]">
              Email
            </Label>
            <Input
              id="email"
              type="text"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); clearEmailError() }}
              autoComplete="email"
              className={
                emailError || apiError
                  ? "h-11 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                  : "h-11 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
              }
            />
            {emailError && (
              <p className="text-xs text-red-500 mt-1.5 pl-1">{emailError}</p>
            )}
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
                placeholder="Min 8 chars, 1 uppercase, 1 number"
                value={password}
                onChange={(e) => { setPassword(e.target.value); clearPasswordError() }}
                autoComplete="new-password"
                className={
                  passwordError || apiError
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
            {(passwordError || apiError) && (
              <p className="text-xs text-red-500 mt-1.5 pl-1">
                {passwordError ?? apiError}
              </p>
            )}
          </div>

          {/* Confirm password */}
          <div className="space-y-1.5">
            <Label htmlFor="confirmPassword" className="text-sm font-medium text-[#374151]">
              Confirm password
            </Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); clearConfirmPasswordError() }}
                autoComplete="new-password"
                className={
                  confirmPasswordError || apiError
                    ? "h-11 pr-10 rounded-xl border border-red-400 bg-red-50 px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-red-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-red-400/20 transition-colors"
                    : "h-11 pr-10 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20 transition-colors"
                }
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-[#6B7280] transition-colors"
              >
                {showConfirmPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
            {(confirmPasswordError || apiError) && (
              <p className="text-xs text-red-500 mt-1.5 pl-1">
                {confirmPasswordError ?? apiError}
              </p>
            )}
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
                Creating account...
              </>
            ) : (
              <>
                Create account
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-[#6B7280]">
          Already have an account?{" "}
          <Link
            href="/login"
            className="text-[#3772FF] hover:text-[#2a5dcc] font-semibold transition-colors"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-white">
          <Loader2 className="w-6 h-6 animate-spin text-[#3772FF]" />
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  )
}
