"use client"
import { useState, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Search, Filter, FileText, Download, Trash2, Eye, ChevronLeft, ChevronRight, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { listTranslations, deleteTranslation } from "@/lib/api"
import type { PaginatedTranslationsResponse, TranslationRow } from "@/lib/types"
import { useConfirm } from "@/hooks/use-confirm"
import { useCrudToast } from "@/hooks/use-crud-toast"

const PAGE_SIZE_OPTIONS = [5, 10, 25] as const
type SortOrder = "newest" | "oldest"

function formatDate(isoString: string): string {
  const d = new Date(isoString)
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

function statusVariant(status: string): { label: string; className: string; dot: "emerald" | "red" | "amber" | "slate" } {
  switch (status) {
    case "done":
      return { label: "Completed", className: "bg-emerald-50 text-emerald-700 border-emerald-100", dot: "emerald" }
    case "failed":
      return { label: "Failed", className: "bg-red-50 text-red-700 border-red-100", dot: "red" }
    case "processing":
    case "queued":
    case "needs_review":
      return { label: status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()), className: "bg-amber-50 text-amber-700 border-amber-100", dot: "amber" }
    default:
      return { label: status, className: "bg-muted text-muted-foreground border-border", dot: "slate" }
  }
}

function DotColor({ color }: { color: "emerald" | "red" | "amber" | "slate" }) {
  return (
    <div
      className={cn(
        "w-1.5 h-1.5 rounded-full",
        color === "emerald" && "bg-emerald-500",
        color === "red" && "bg-red-500",
        color === "amber" && "bg-amber-500",
        color === "slate" && "bg-zinc-500 dark:bg-zinc-400"
      )}
    />
  )
}

export default function HistoryPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<5 | 10 | 25>(10)
  const [sort, setSort] = useState<SortOrder>("newest")
  const [search, setSearch] = useState("")
  const queryClient = useQueryClient()
  const crud = useCrudToast()
  const confirm = useConfirm()

  const { data, isLoading, isError, error } = useQuery<PaginatedTranslationsResponse>({
    queryKey: ["translations", { page, size: pageSize, sort }],
    queryFn: () => listTranslations({ page, size: pageSize, sort: sort === "newest" ? "-created_at" : "created_at" }),
    placeholderData: (prev) => prev,
  })

  const deleteMutation = useMutation({
    mutationFn: async (jobId: string) => {
      await deleteTranslation(jobId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["translations"] })
      crud.deleted("Translation")
    },
    onError: (err: Error) => {
      crud.failed("delete", "translation", err)
    },
  })

  const handleDeleteJob = async (job: TranslationRow) => {
    const ok = await confirm({
      title: "Delete translation?",
      description: (
        <>
          This will permanently delete <strong>{job.filename}</strong>. This cannot be undone.
        </>
      ),
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (ok) deleteMutation.mutate(job.job_id)
  }

  // Filter client-side from the already-fetched page
  const filteredRows: TranslationRow[] = data?.rows ?? []
  const jobs = search.trim()
    ? filteredRows.filter((j) =>
        j.filename.toLowerCase().includes(search.toLowerCase())
      )
    : filteredRows

  const total = data?.total ?? 0
  const totalPages = data?.total_pages ?? 0

  const handlePageSizeChange = useCallback((size: 5 | 10 | 25) => {
    setPageSize(size)
    setPage(1) // reset to first page when page size changes
  }, [])

  const handleSortChange = useCallback((s: SortOrder) => {
    setSort(s)
    setPage(1)
  }, [])

  return (
    <div className="space-y-6 p-6 md:p-8 lg:p-10 overflow-y-auto h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Translation History</h1>
            <p className="text-muted-foreground mt-1">Manage and access all your past file translations.</p>
          </div>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden flex flex-col">
          {/* Toolbar */}
          <div className="p-4 border-b border-border flex flex-col sm:flex-row gap-4 justify-between bg-muted/50">
            <div className="relative max-w-sm w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search files..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                className="w-full bg-card border border-border rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
              />
            </div>
            <div className="flex items-center gap-3">
              <select
                value={sort}
                onChange={(e) => handleSortChange(e.target.value as SortOrder)}
                className="bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            {isLoading && (
              <div className="flex items-center justify-center py-20 text-muted-foreground">
                <Loader2 className="w-6 h-6 animate-spin mr-2" />
                Loading...
              </div>
            )}
            {isError && (
              <div className="flex items-center justify-center py-20 text-red-500 text-sm">
                Failed to load jobs: {(error as Error).message}
              </div>
            )}
            {!isLoading && !isError && jobs.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-2">
                <FileText className="w-10 h-10 opacity-30" />
                <p className="text-sm">{search ? "No files match your search." : "No translations yet."}</p>
              </div>
            )}
            {!isLoading && !isError && jobs.length > 0 && (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-muted border-b border-border text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    <th className="px-6 py-4">File Name</th>
                    <th className="px-6 py-4">Language Pair</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Date &amp; Time</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {jobs.map((job) => {
                    const sv = statusVariant(job.status)
                    return (
                      <tr key={job.job_id} className="hover:bg-muted/80 transition group">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-primary/10 text-primary rounded-lg">
                              <FileText className="w-4 h-4" />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground truncate max-w-[200px]" title={job.filename}>
                                {job.filename}
                              </p>
                              <p className="text-xs text-muted-foreground capitalize">
                                {job.input_format}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2 text-sm text-foreground">
                            <span className="bg-muted px-2 py-1 rounded text-xs font-medium text-muted-foreground">
                              {job.source_lang === "auto" ? "Auto" : job.source_lang}
                            </span>
                            <span className="text-muted-foreground">&rarr;</span>
                            <span className="bg-primary/10 px-2 py-1 rounded text-xs font-medium text-primary">
                              {job.target_lang}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={cn("px-2.5 py-1 rounded-full text-xs font-medium inline-flex items-center gap-1.5 border", sv.className)}>
                            <DotColor color={sv.dot} />
                            {sv.label}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatDate(job.created_at)}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition">
                            <a
                              href={`/jobs/${job.job_id}`}
                              className="p-1.5 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md transition"
                              title="View details"
                            >
                              <Eye className="w-4 h-4" />
                            </a>
                            {(job.status === "done" || job.status === "needs_review") && (
                              <a
                                href={`/api/v1/jobs/${job.job_id}/download`}
                                className="p-1.5 text-muted-foreground hover:text-emerald-600 hover:bg-emerald-50 rounded-md transition"
                                title="Download"
                              >
                                <Download className="w-4 h-4" />
                              </a>
                            )}
                            <button
                              className="p-1.5 text-muted-foreground hover:text-red-600 hover:bg-red-50 rounded-md transition"
                              title="Delete"
                              onClick={() => handleDeleteJob(job)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination footer */}
          {!isLoading && !isError && total > 0 && (
            <div className="p-4 border-t border-border bg-muted flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>
                  Showing {Math.min((page - 1) * pageSize + 1, total)} to{" "}
                  {Math.min(page * pageSize, total)} of {total} entries
                </span>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground">Rows:</span>
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <button
                      key={size}
                      onClick={() => handlePageSizeChange(size)}
                      className={cn(
                        "px-2 py-1 rounded text-xs font-medium transition",
                        pageSize === size
                          ? "bg-primary/10 text-primary border border-primary/20 dark:border-primary/30"
                          : "bg-card border border-border text-muted-foreground hover:bg-muted"
                      )}
                    >
                      {size}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-1.5 border border-border bg-card rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  // Show page window centred around current page
                  const start = Math.max(1, Math.min(page - 2, totalPages - 4))
                  const p = start + i
                  if (p > totalPages) return null
                  return (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      className={cn(
                        "w-8 h-8 rounded-md text-xs font-medium transition",
                        page === p
                          ? "bg-primary text-primary-foreground"
                          : "bg-card border border-border text-muted-foreground hover:bg-muted"
                      )}
                    >
                      {p}
                    </button>
                  )
                })}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-1.5 border border-border bg-card rounded-md hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
