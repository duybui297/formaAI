import type { Metadata } from "next"

export const metadata: Metadata = {
  title: {
    default: "Sign in — Forma",
    template: "%s — Forma",
  },
  description: "Sign in to your Forma account",
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
