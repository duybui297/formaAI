"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { AppSidebar } from "@/components/layout/AppSidebar"
import { Loader2 } from "lucide-react"

const AUTH_COOKIE = "forma_access_token"

function isAuthenticated(): boolean {
  if (typeof document === "undefined") return false
  return document.cookie.includes(`${AUTH_COOKIE}=`)
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login")
    } else {
      setChecking(false)
    }
  }, [router])

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-white">
        <Loader2 className="w-6 h-6 animate-spin text-[#3772FF]" />
      </div>
    )
  }

  return <AppSidebar>{children}</AppSidebar>
}
