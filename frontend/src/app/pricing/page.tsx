"use client"
import { CheckCircle2, Zap } from "lucide-react"

const plans = [
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
    buttonText: "Current Plan",
    buttonVariant: "outline" as const,
    popular: false,
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
  },
]

export default function PricingPage() {
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {plans.map((plan, i) => (
          <div
            key={i}
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
              className={`w-full py-3 px-4 rounded-xl font-semibold transition-all shadow-sm ${
                plan.buttonVariant === "solid"
                  ? "bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-md"
                  : "bg-white text-zinc-900 border border-zinc-200 hover:bg-zinc-50"
              }`}
            >
              {plan.buttonText}
            </button>
          </div>
        ))}
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
    </div>
  )
}
