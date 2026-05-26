"use client"
import { Search, Filter, FileText, Download, Trash2, Eye } from "lucide-react"
import { cn } from "@/lib/utils"

const historyData = [
  { id: "1", name: "Annual_Report_2023.pdf", source: "English", target: "French", status: "Completed", date: "Oct 24, 2023", duration: "45s", credits: 12 },
  { id: "2", name: "Q3_Financials.xlsx", source: "English", target: "Spanish", status: "Completed", date: "Oct 23, 2023", duration: "12s", credits: 4 },
  { id: "3", name: "User_Manual_v4.docx", source: "Auto", target: "German", status: "Failed", date: "Oct 20, 2023", duration: "1m 20s", credits: 0 },
  { id: "4", name: "Meeting_Notes.txt", source: "English", target: "Japanese", status: "Completed", date: "Oct 19, 2023", duration: "5s", credits: 2 },
  { id: "5", name: "Contract_Agreement.pdf", source: "Spanish", target: "English", status: "Processing", date: "Oct 19, 2023", duration: "-", credits: "-" as unknown as number },
]

export default function HistoryPage() {
  return (
    <div className="space-y-6 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-zinc-900">Translation History</h1>
            <p className="text-zinc-500 mt-1">Manage and access all your past file translations.</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b border-zinc-200 flex flex-col sm:flex-row gap-4 justify-between bg-zinc-50/50">
            <div className="relative max-w-sm w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search files..."
                className="w-full bg-white border border-zinc-200 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition"
              />
            </div>
            <button className="flex items-center justify-center gap-2 bg-white border border-zinc-200 text-zinc-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-zinc-50 transition">
              <Filter className="w-4 h-4" />
              Filter
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-50 border-b border-zinc-200 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                  <th className="px-6 py-4">File Name</th>
                  <th className="px-6 py-4">Language Pair</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Date &amp; Time</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200">
                {historyData.map((item) => (
                  <tr key={item.id} className="hover:bg-zinc-50/80 transition group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-zinc-900">{item.name}</p>
                          <p className="text-xs text-zinc-500">{item.duration} &bull; {item.credits} credits</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm text-zinc-700">
                        <span className="bg-zinc-100 px-2 py-1 rounded text-xs font-medium text-zinc-600">{item.source}</span>
                        <span className="text-zinc-400">&rarr;</span>
                        <span className="bg-indigo-50 px-2 py-1 rounded text-xs font-medium text-indigo-700">{item.target}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={cn(
                          "px-2.5 py-1 rounded-full text-xs font-medium inline-flex items-center gap-1.5",
                          item.status === "Completed" && "bg-emerald-50 text-emerald-700 border border-emerald-100",
                          item.status === "Failed" && "bg-red-50 text-red-700 border border-red-100",
                          item.status === "Processing" && "bg-amber-50 text-amber-700 border border-amber-100"
                        )}
                      >
                        {item.status === "Completed" && <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                        {item.status === "Failed" && <div className="w-1.5 h-1.5 rounded-full bg-red-500" />}
                        {item.status === "Processing" && <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />}
                        {item.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-zinc-500">{item.date}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition">
                        <button className="p-1.5 text-zinc-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition" title="Preview">
                          <Eye className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 text-zinc-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-md transition" title="Download">
                          <Download className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 text-zinc-400 hover:text-red-600 hover:bg-red-50 rounded-md transition" title="Delete">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-zinc-200 bg-zinc-50 flex items-center justify-between text-sm text-zinc-500">
            <p>Showing 1 to 5 of 24 entries</p>
            <div className="flex gap-2">
              <button className="px-3 py-1 border border-zinc-200 bg-white rounded-md hover:bg-zinc-50 disabled:opacity-50">Previous</button>
              <button className="px-3 py-1 border border-zinc-200 bg-white rounded-md hover:bg-zinc-50">Next</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
