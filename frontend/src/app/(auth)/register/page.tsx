"use client"
import { useState } from "react"
import Link from "next/link"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { Eye, EyeOff, Loader2, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { registerApi, loginApi, setToken, setStoredUser, setAuthCookie } from "@/lib/auth"

export default function RegisterPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirmPassword: "",
  })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match")
      return
    }
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }

    setLoading(true)
    try {
      await registerApi({
        email: form.email,
        password: form.password,
        full_name: form.full_name || undefined,
      })
      const result = await loginApi({ email: form.email, password: form.password })
      setToken(result.access_token)
      setAuthCookie(result.access_token)
      const meRes = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${result.access_token}` },
      })
      if (meRes.ok) {
        setStoredUser(await meRes.json())
      }
      router.push("/translator")
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <div className="w-full max-w-[360px]">

        {/* Mobile logo */}
        <div className="flex lg:hidden items-center gap-2 mb-10">
          <div className="relative w-9 h-9 shrink-0">
            <Image src="/assets/brand/logo.png" alt="Forma" fill className="object-contain" />
          </div>
          <span className="font-bold text-xl text-[#0C1B33]">Forma</span>
        </div>

        {/* Heading */}
        <div className="space-y-1 mb-8">
          <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33]">
            Create your account
          </h2>
          <p className="text-sm text-[#6B7280]">
            Start translating documents today
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-5">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
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
              placeholder="Nguyen Van A"
              value={form.full_name}
              onChange={(e) => update("full_name", e.target.value)}
              autoComplete="name"
              className="h-11 rounded-xl border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827]
                placeholder:text-[#9CA3AF]
                focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20
                transition-colors"
            />
          </div>

          {/* Email */}
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-sm font-medium text-[#374151]">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              required
              autoComplete="email"
              className="h-11 rounded-xl border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827]
                placeholder:text-[#9CA3AF]
                focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20
                transition-colors"
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
                placeholder="Min. 8 characters"
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                className="h-11 pr-10 rounded-xl border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827]
                  placeholder:text-[#9CA3AF]
                  focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20
                  transition-colors"
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
          </div>

          {/* Confirm password */}
          <div className="space-y-1.5">
            <Label htmlFor="confirmPassword" className="text-sm font-medium text-[#374151]">
              Confirm password
            </Label>
            <Input
              id="confirmPassword"
              type={showPassword ? "text" : "password"}
              placeholder="Repeat password"
              value={form.confirmPassword}
              onChange={(e) => update("confirmPassword", e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="h-11 rounded-xl border-[#E5E7EB] bg-[#F9FAFB] px-4 text-sm text-[#111827]
                placeholder:text-[#9CA3AF]
                focus:border-[#3772FF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3772FF]/20
                transition-colors"
            />
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
