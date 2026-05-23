"use client"
import {
  User,
  Building,
  Key,
  Bell,
  Languages,
  ShieldCheck,
  CreditCard,
} from "lucide-react"

const settingsNav = [
  { id: "profile", label: "Profile", icon: User, active: true },
  { id: "workspace", label: "Team Workspace", icon: Building, active: false },
  { id: "api", label: "API Keys", icon: Key, active: false },
  { id: "translation", label: "Translation Defaults", icon: Languages, active: false },
  { id: "notifications", label: "Notifications", icon: Bell, active: false },
  { id: "billing", label: "Billing", icon: CreditCard, active: false },
  { id: "security", label: "Security", icon: ShieldCheck, active: false },
]

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-5xl p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Settings</h1>
        <p className="text-zinc-500 mt-1">Manage your account preferences and translation defaults.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Settings Navigation */}
        <div className="w-full md:w-64 shrink-0 space-y-1">
          {settingsNav.map((item) => (
            <button
              key={item.id}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                item.active
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              <item.icon className={`w-4 h-4 ${item.active ? "text-zinc-900" : "text-zinc-400"}`} />
              {item.label}
            </button>
          ))}
        </div>

        {/* Settings Content */}
        <div className="flex-1 space-y-6">
          <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
            <div className="p-6 border-b border-zinc-200">
              <h2 className="text-lg font-semibold text-zinc-900">Personal Information</h2>
              <p className="text-sm text-zinc-500 mt-1">Update your basic profile information and email.</p>
            </div>

            <div className="p-6 space-y-6">
              <div className="flex items-center gap-6">
                <div className="w-20 h-20 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-2xl font-bold border-4 border-white shadow-sm ring-1 ring-zinc-200">
                  AI
                </div>
                <div>
                  <button className="bg-white border border-zinc-200 px-4 py-2 rounded-lg text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition shadow-sm">
                    Change Avatar
                  </button>
                  <p className="text-xs text-zinc-500 mt-2">JPG, GIF or PNG. Max size of 2MB.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700">First Name</label>
                  <input
                    type="text"
                    defaultValue="AI"
                    className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-zinc-700">Last Name</label>
                  <input
                    type="text"
                    defaultValue="Core"
                    className="w-full bg-white border border-zinc-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <label className="text-sm font-medium text-zinc-700">Email Address</label>
                  <input
                    type="email"
                    defaultValue="admin@aicore.com"
                    className="w-full bg-zinc-50 border border-zinc-300 rounded-lg px-3 py-2 text-zinc-500 cursor-not-allowed"
                    disabled
                  />
                </div>
              </div>
            </div>
            <div className="p-4 bg-zinc-50 border-t border-zinc-200 flex justify-end rounded-b-xl gap-3">
              <button className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900">Cancel</button>
              <button className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm">Save Changes</button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-zinc-200 shadow-sm">
            <div className="p-6 border-b border-zinc-200">
              <h2 className="text-lg font-semibold text-zinc-900">Appearance</h2>
              <p className="text-sm text-zinc-500 mt-1">Customize how the interface looks on your device.</p>
            </div>
            <div className="p-6 flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-900">Theme Preference</p>
                <p className="text-sm text-zinc-500 mt-1">Currently using the Light theme.</p>
              </div>
              <div className="flex bg-zinc-100 p-1 rounded-lg">
                <button className="px-3 py-1.5 bg-white text-zinc-900 text-sm font-medium rounded shadow-sm">Light</button>
                <button className="px-3 py-1.5 text-zinc-500 hover:text-zinc-900 text-sm font-medium rounded transition">Dark</button>
                <button className="px-3 py-1.5 text-zinc-500 hover:text-zinc-900 text-sm font-medium rounded transition">System</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
