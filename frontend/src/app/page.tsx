"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

function getAccessToken(): string | null {
  if (typeof document === "undefined") return null
  const match = document.cookie.match(/(?:^|;\s*)forma_access_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

export default function HomePage() {
  const router = useRouter()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    async function go() {
      const token = getAccessToken()
      if (token) {
        try {
          const res = await fetch("/api/auth/me", {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (res.ok) {
            router.push("/translator")
            return
          }
        } catch {
          // fall through to login
        }
      }
      router.push("/login")
    }
    go()
    setReady(true)
  }, [router])

  if (!ready) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return null
}
