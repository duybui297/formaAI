"use client"
import { useState } from "react"
import { CheckCircle2, Zap, Loader2 } from "lucide-react"
import Link from "next/link"
import { checkoutLicense } from "@/lib/api"
import type { CheckoutPlan, CheckoutLicenseResponse } from "@/lib/types"

/** Tier labels as returned by the backend checkout endpoint */
type CheckoutTier = "TRIAL" | "PRO" | "ENTERPRISE"
import { OneTimeKeyDialog } from "@/features/licenses/OneTimeKeyDialog"

const plans: {
  name: string
  price: string
  interval: string
  description: string
  features: string[]
  buttonText: string
  buttonVariant: "solid" | "outline"
  popular: boolean
  plan: CheckoutPlan
  tier: CheckoutTier
}[] = [
  {
    name: "Free",
    price: "$0",
    interval: "forever",
    description: "Perfect for exploring our AI translation capabilities.",
    features: [
      "10 documents per month",
      "Standard translation quality",
      "Max file size: 5MB",
      "Community support",
      "Preserves basic formatting",
    ],
    buttonText: "Get Started Free",
    buttonVariant: "outline" as const,
    popular: false,
    plan: "free",
    tier: "TRIAL",
  },
  {
    name: "Pro",
    price: "$29",
    interval: "per month",
    description: "Ideal for professionals needing regular translations.",
    features: [
      "Unlimited document translations",
      "High-precision AI models",
      "Max file size: 50MB",
      "Priority email support",
      "Advanced formatting preservation",
      "Glossary & terminology support",
      "OCR for scanned documents",
    ],
    buttonText: "Upgrade to Pro",
    buttonVariant: "solid" as const,
    popular: true,
    plan: "pro",
    tier: "PRO",
  },
  {
    name: "Business",
    price: "$99",
    interval: "per month / up to 5 users",
    description: "Built for teams scaling global content operations.",
    features: [
      "Everything in Pro",
      "Team collaboration & shared glossaries",
      "API access (10k credits/mo)",
      "Max file size: 100MB",
      "Dedicated account manager",
      "SSO & advanced security",
      "Bulk batch processing",
    ],
    buttonText: "Start 14-day Trial",
    buttonVariant: "outline" as const,
    popular: false,
    plan: "business",
    tier: "ENTERPRISE",
  },
]

export default function PricingPage() {
  const [loadingPlan, setLoadingPlan] = useState<CheckoutPlan | null>(null)
  const [dialogKey, setDialogKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleCheckout(plan: CheckoutPlan) {
    setLoadingPlan(plan)
    setError(null)
    try {
      const result: CheckoutLicenseResponse = await checkoutLicense(plan)
      setDialogKey(result.raw_key)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed")
    } finally {
      setLoadingPlan(null)
    }
  }

  return (
    <div className="space-y-12 pb-12 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="text-center max-w-2xl mx-auto space-y-4 pt-8">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-zinc-900">
          Simple, transparent pricing
        </h1>
        <p className="text-lg text-zinc-500">
          Choose the plan that best fits your translation volume and professional requirements. No hidden fees.
        </p>

        <div className="flex items-center justify-center gap-3 mt-8">
          <span className="text-sm font-medium text-zinc-900">Monthly</span>
          <button className="relative inline-flex h-6 w-11 items-center rounded-full bg-indigo-600 transition-colors">
            <span className="translate-x-6 inline-block h-4 w-4 transform rounded-full bg-white transition-transform" />
          </button>
          <span className="text-sm font-medium text-zinc-500 flex items-center gap-1.5">
            Yearly{" "}
            <span className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full font-bold">
              Save 20%
            </span>
          </span>
        </div>
      </div>

      {error && (
        <div className="max-w-6xl mx-auto">
          <p className="text-sm text-red-600 text-center bg-red-50 border border-red-200 rounded-lg px-4 py-2">
            {error}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {plans.map((plan, i) => {
          const isLoading = loadingPlan === plan.plan
          return (
            <div
              key={i}
              data-tier={plan.tier}
              data-plan={plan.plan}
              className={`relative p-8 bg-white rounded-3xl border shadow-sm flex flex-col ${
                plan.popular
                  ? "border-indigo-600 shadow-indigo-100 shadow-xl ring-1 ring-indigo-600"
                  : "border-zinc-200"
              }`}
            >
              {plan.popular && (
                <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2">
                  <span className="bg-indigo-600 text-white text-xs font-bold uppercase tracking-wider py-1 px-3 rounded-full flex items-center gap-1">
                    <Zap className="w-3 h-3 fill-current" /> Most Popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-xl font-semibold text-zinc-900">{plan.name}</h3>
                <p className="text-xs font-medium text-indigo-600 mt-1">
                  License: {plan.tier}
                </p>
                <p className="text-sm text-zinc-500 mt-2 min-h-[40px]">{plan.description}</p>
              </div>

              <div className="mb-8 border-b border-zinc-100 pb-8 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-bold text-zinc-900">{plan.price}</span>
                  <span className="text-sm font-medium text-zinc-500">{plan.interval}</span>
                </div>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-3 text-sm text-zinc-700">
                    <CheckCircle2 className="w-5 h-5 text-indigo-600 shrink-0" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                data-testid={`checkout-btn-${plan.plan}`}
                disabled={isLoading || loadingPlan !== null}
                onClick={() => handleCheckout(plan.plan)}
                className={`w-full py-3 px-4 rounded-xl font-semibold transition-all shadow-sm flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed ${
                  plan.buttonVariant === "solid"
                    ? "bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-md"
                    : "bg-white text-zinc-900 border border-zinc-200 hover:bg-zinc-50"
                }`}
              >
                {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                {plan.buttonText}
              </button>
            </div>
          )
        })}
      </div>

      <div className="max-w-3xl mx-auto text-center mt-12 bg-zinc-50 border border-zinc-200 rounded-2xl p-8">
        <h3 className="text-xl font-semibold text-zinc-900 mb-2">Need a custom enterprise solution?</h3>
        <p className="text-zinc-600 mb-6">
          Access unlimited API credits, on-premise deployment options, and custom SLA agreements.
        </p>
        <button className="bg-zinc-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-zinc-800 transition shadow-sm">
          Contact Sales
        </button>
      </div>

      {/* One-time key dialog — shown after successful checkout */}
      <OneTimeKeyDialog
        open={dialogKey !== null}
        rawKey={dialogKey ?? ""}
        onClose={() => setDialogKey(null)}
        extraContent={
          <p className="text-sm text-zinc-600 mt-2">
            Ready to use your key?{" "}
            <Link
              href="/activate"
              data-testid="activate-link"
              className="text-indigo-600 underline hover:text-indigo-700 font-medium"
            >
              Activate now
            </Link>
          </p>
        }
      />
    </div>
  )
}
