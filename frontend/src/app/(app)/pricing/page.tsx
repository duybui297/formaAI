"use client"
import { useState } from "react"
import { CheckCircle2, Zap, Loader2, X } from "lucide-react"
import { submitLead } from "@/lib/api"
import type { CheckoutPlan } from "@/lib/types"

/** Tier labels as returned by the backend checkout endpoint */
type CheckoutTier = "TRIAL" | "PRO" | "ENTERPRISE"

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

// ---------------------------------------------------------------------------
// LeadCaptureDialog
// ---------------------------------------------------------------------------

interface LeadCaptureDialogProps {
  open: boolean
  plan: CheckoutPlan | null
  onClose: () => void
}

function LeadCaptureDialog({ open, plan, onClose }: LeadCaptureDialogProps) {
  const [email, setEmail] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  function handleClose() {
    setEmail("")
    setError(null)
    setSubmitted(false)
    onClose()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!plan) return
    setSubmitting(true)
    setError(null)
    try {
      await submitLead(email, plan)
      setSubmitted(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed")
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const planName = plans.find((p) => p.plan === plan)?.name ?? plan

  return (
    <div
      data-testid="lead-capture-dialog"
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={handleClose}
        aria-hidden="true"
      />

      <div className="relative bg-card rounded-2xl shadow-xl w-full max-w-md p-8 space-y-6">
        <button
          type="button"
          onClick={handleClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {submitted ? (
          <div data-testid="lead-capture-success" className="text-center space-y-3">
            <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto" />
            <h2 className="text-xl font-semibold text-foreground">
              Thanks — we&apos;ll be in touch!
            </h2>
            <p className="text-sm text-muted-foreground">
              Cảm ơn! Chúng tôi sẽ liên hệ ưu đãi sớm.
            </p>
            <button
              type="button"
              onClick={handleClose}
              className="mt-4 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-1">
              <h2 className="text-xl font-semibold text-foreground">
                Interested in the <span className="text-primary">{planName}</span> plan?
              </h2>
              <p className="text-sm text-muted-foreground">
                Leave your email and we&apos;ll reach out with your offer.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="lead-email"
                  className="text-sm font-medium text-foreground"
                >
                  Email address
                </label>
                <input
                  id="lead-email"
                  data-testid="lead-email-input"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    setError(null)
                  }}
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              {error && (
                <p
                  data-testid="lead-capture-error"
                  className="text-sm text-red-600"
                >
                  {error}
                </p>
              )}

              <button
                type="submit"
                data-testid="lead-capture-submit"
                disabled={submitting || !email.trim()}
                className="w-full py-2.5 rounded-xl bg-primary text-primary-foreground font-semibold text-sm hover:bg-primary/90 transition disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                Send my details
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// PricingPage
// ---------------------------------------------------------------------------

export default function PricingPage() {
  const [leadPlan, setLeadPlan] = useState<CheckoutPlan | null>(null)

  return (
    <div className="space-y-12 pb-12 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="text-center max-w-2xl mx-auto space-y-4 pt-8">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground">
          Simple, transparent pricing
        </h1>
        <p className="text-lg text-muted-foreground">
          Choose the plan that best fits your translation volume and professional requirements. No hidden fees.
        </p>

        <div className="flex items-center justify-center gap-3 mt-8">
          <span className="text-sm font-medium text-foreground">Monthly</span>
          <button className="relative inline-flex h-6 w-11 items-center rounded-full bg-primary transition-colors">
            <span className="translate-x-6 inline-block h-4 w-4 transform rounded-full bg-card transition-transform" />
          </button>
          <span className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
            Yearly{" "}
            <span className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300 text-xs px-2 py-0.5 rounded-full font-bold">
              Save 20%
            </span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {plans.map((plan, i) => (
          <div
            key={i}
            data-tier={plan.tier}
            data-plan={plan.plan}
            className={`relative p-8 bg-card rounded-3xl border shadow-sm flex flex-col ${
              plan.popular
                ? "border-primary dark:border-primary/80 shadow-primary/20 dark:shadow-primary/40 shadow-xl ring-1 ring-primary dark:ring-primary/80"
                : "border-border dark:border-border/80"
            }`}
          >
            {plan.popular && (
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2">
                <span className="bg-primary text-primary-foreground text-xs font-bold uppercase tracking-wider py-1 px-3 rounded-full flex items-center gap-1">
                  <Zap className="w-3 h-3 fill-current" /> Most Popular
                </span>
              </div>
            )}

            <div className="mb-6">
              <h3 className="text-xl font-semibold text-foreground">{plan.name}</h3>
              <p className="text-xs font-medium text-primary dark:text-primary/70 mt-1">
                License: {plan.tier}
              </p>
              <p className="text-sm text-muted-foreground mt-2 min-h-[40px]">{plan.description}</p>
            </div>

            <div className="mb-8 border-b border-b-border pb-8 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-4xl font-bold text-foreground">{plan.price}</span>
                <span className="text-sm font-medium text-muted-foreground">{plan.interval}</span>
              </div>
            </div>

            <ul className="space-y-4 mb-8">
              {plan.features.map((feature, idx) => (
                <li key={idx} className="flex items-start gap-3 text-sm text-foreground">
                  <CheckCircle2 className="w-5 h-5 text-primary shrink-0" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>

            <button
              data-testid={`checkout-btn-${plan.plan}`}
              onClick={() => setLeadPlan(plan.plan)}
              className={`w-full py-3 px-4 rounded-xl font-semibold transition-all shadow-sm flex items-center justify-center gap-2 ${
                plan.buttonVariant === "solid"
                  ? "bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-md"
                  : "bg-card text-foreground border border-border hover:bg-muted"
              }`}
            >
              {plan.buttonText}
            </button>
          </div>
        ))}
      </div>

      <div className="max-w-3xl mx-auto text-center mt-12 bg-muted border border-border rounded-2xl p-8">
        <h3 className="text-xl font-semibold text-foreground mb-2">Need a custom enterprise solution?</h3>
        <p className="text-muted-foreground mb-6">
          Access unlimited API credits, on-premise deployment options, and custom SLA agreements.
        </p>
        <button className="bg-foreground text-background px-6 py-2.5 rounded-lg font-medium hover:bg-foreground/10 transition shadow-sm">
          Contact Sales
        </button>
      </div>

      <LeadCaptureDialog
        open={leadPlan !== null}
        plan={leadPlan}
        onClose={() => setLeadPlan(null)}
      />
    </div>
  )
}
