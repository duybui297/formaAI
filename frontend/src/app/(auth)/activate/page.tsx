import type { Metadata } from "next"
import { ActivateForm } from "@/features/licenses/ActivateForm"

export const metadata: Metadata = {
  title: "Activate License — Forma",
  description: "Activate your Forma license key",
}

export default function ActivatePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-6">
      <div className="w-full max-w-[400px]">
        <div className="text-center mb-8">
          <h1 className="text-[28px] font-bold leading-tight text-[#0C1B33] mb-1 font-[var(--font-montserrat)]">
            Activate License
          </h1>
          <p className="text-sm text-[#6B7280]">
            Enter your license key to unlock Forma.
          </p>
        </div>

        <ActivateForm />
      </div>
    </div>
  )
}
