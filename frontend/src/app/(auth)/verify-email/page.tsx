"use client"
import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

type Status = "loading" | "success" | "error"

function VerifyEmailContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")
  const [status, setStatus] = useState<Status>("loading")
  const [message, setMessage] = useState("Verifying your email...")

  useEffect(() => {
    if (!token) {
      setStatus("error")
      setMessage("Missing verification token. Please use the link from your email.")
      return
    }

    async function verify() {
      try {
        const res = await fetch("/api/v1/auth/verify-email", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        })
        const data = await res.json().catch(() => ({}))
        if (res.ok) {
          setStatus("success")
          setMessage(data.message || "Email verified successfully.")
          // Auto-redirect to login after 3s
          setTimeout(() => router.push("/login"), 3000)
        } else {
          setStatus("error")
          setMessage(data.detail || "Verification failed. The link may have expired.")
        }
      } catch {
        setStatus("error")
        setMessage("Network error. Please try again.")
      }
    }
    verify()
  }, [token, router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <div className="w-full max-w-[420px] text-center">
        <div className="flex justify-center mb-6">
          {status === "loading" && (
            <Loader2 className="w-16 h-16 text-[#3772FF] animate-spin" />
          )}
          {status === "success" && (
            <CheckCircle2 className="w-16 h-16 text-emerald-500" />
          )}
          {status === "error" && (
            <XCircle className="w-16 h-16 text-red-500" />
          )}
        </div>

        <h2 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-3">
          {status === "loading" && "Verifying..."}
          {status === "success" && "Email verified"}
          {status === "error" && "Verification failed"}
        </h2>

        <p className="text-sm text-[#6B7280] mb-8 leading-relaxed">
          {message}
        </p>

        {status === "success" && (
          <p className="text-xs text-[#9CA3AF] mb-4">
            Redirecting to sign in in a few seconds...
          </p>
        )}

        {status !== "loading" && (
          <Button
            type="button"
            onClick={() => router.push("/login")}
            className="w-full h-11 rounded-xl text-sm font-semibold text-white
              bg-[#3772FF] hover:bg-[#2a5dcc] transition-colors shadow-sm"
          >
            Go to sign in
          </Button>
        )}

        {status === "error" && (
          <p className="mt-4 text-xs text-[#9CA3AF]">
            Need an account?{" "}
            <Link
              href="/signup"
              className="text-[#3772FF] hover:text-[#2a5dcc] font-semibold"
            >
              Sign up
            </Link>
          </p>
        )}
      </div>
    </div>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-white">
          <Loader2 className="w-6 h-6 animate-spin text-[#3772FF]" />
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  )
}
