"use client"
import {
  FileText,
  UploadCloud,
  TrendingUp,
  CreditCard,
  Bell,
  CheckCircle2,
  AlertCircle,
} from "lucide-react"

const chartData = [
  { name: "Jan", words: 40000 },
  { name: "Feb", words: 30000 },
  { name: "Mar", words: 20000 },
  { name: "Apr", words: 27800 },
  { name: "May", words: 18900 },
  { name: "Jun", words: 23900 },
  { name: "Jul", words: 34900 },
]

const maxWords = Math.max(...chartData.map((d) => d.words))

export default function DashboardPage() {
  return (
    <div className="space-y-6 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Dashboard</h1>
            <p className="text-zinc-500 mt-1">
              Welcome back! Here&apos;s an overview of your translation activity.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 transition">
              <UploadCloud className="w-4 h-4" />
              Quick Upload
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Files Translated", value: "1,234", icon: FileText, color: "text-indigo-600", bg: "bg-indigo-50" },
            { label: "Words Processed", value: "45.2k", icon: TrendingUp, color: "text-emerald-600", bg: "bg-emerald-50" },
            { label: "Credits Remaining", value: "8,450", icon: CreditCard, color: "text-amber-600", bg: "bg-amber-50" },
            { label: "Active Plan", value: "Pro", icon: CheckCircle2, color: "text-purple-600", bg: "bg-purple-50" },
          ].map((stat, i) => (
            <div key={i} className="bg-white p-6 rounded-xl border border-zinc-200 shadow-sm flex items-center gap-4">
              <div className={`p-3 rounded-lg ${stat.bg} ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-500">{stat.label}</p>
                <p className="text-2xl font-bold text-zinc-900">{stat.value}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chart — CSS bar chart (no recharts dep) */}
          <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-zinc-200 shadow-sm">
            <h2 className="text-lg font-semibold text-zinc-900 mb-6">Translation Volume</h2>
            <div className="h-[300px] flex items-end gap-3 px-2">
              {chartData.map((d) => (
                <div key={d.name} className="flex-1 flex flex-col items-center gap-2">
                  <span className="text-xs text-zinc-500">{(d.words / 1000).toFixed(0)}k</span>
                  <div
                    className="w-full bg-indigo-600 rounded-t-md transition-all"
                    style={{ height: `${(d.words / maxWords) * 240}px` }}
                  />
                  <span className="text-xs text-zinc-500">{d.name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-white p-6 rounded-xl border border-zinc-200 shadow-sm">
              <h2 className="text-lg font-semibold text-zinc-900 mb-4 flex items-center gap-2">
                <Bell className="w-5 h-5 text-indigo-600" />
                Notifications
              </h2>
              <div className="space-y-4">
                {[
                  { title: "Translation complete", desc: "Q3_Report_Final.pptx is ready", time: "10m ago", icon: CheckCircle2, color: "text-emerald-500" },
                  { title: "Credit low", desc: "You have used 80% of your allowance", time: "2h ago", icon: AlertCircle, color: "text-amber-500" },
                  { title: "New language added", desc: "We now support Icelandic!", time: "1d ago", icon: Bell, color: "text-indigo-500" },
                ].map((notif, i) => (
                  <div key={i} className="flex gap-3 items-start">
                    <notif.icon className={`w-5 h-5 mt-0.5 ${notif.color}`} />
                    <div>
                      <p className="text-sm font-medium text-zinc-900">{notif.title}</p>
                      <p className="text-sm text-zinc-500">{notif.desc}</p>
                      <p className="text-xs text-zinc-400 mt-1">{notif.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-indigo-600 text-white p-6 rounded-xl border border-indigo-500 shadow-sm relative overflow-hidden">
              <div className="relative z-10">
                <h2 className="text-lg font-semibold mb-2">Pro Tip</h2>
                <p className="text-indigo-100 text-sm mb-4">
                  Did you know? You can upload custom glossaries to ensure technical terms are always translated exactly how you want them.
                </p>
                <button className="text-sm font-medium bg-white/20 hover:bg-white/30 transition px-3 py-1.5 rounded-md">
                  Manage Glossaries
                </button>
              </div>
              <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-white/10 rounded-full blur-2xl" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
