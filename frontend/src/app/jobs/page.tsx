"use client"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { JobsTable } from "@/components/JobsTable"
import { NavBar } from "@/components/NavBar"
import { listJobs } from "@/lib/api"

export default function JobsPage() {
  const router = useRouter()
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: listJobs,
    refetchInterval: 5_000, // poll every 5s — jobs list has no SSE
  })

  return (
    <>
      <NavBar />
      <main className="max-w-3xl mx-auto px-8 py-12 space-y-6">
        {/* Heading row */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900">Translation Jobs</h1>
          <Button
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            onClick={() => router.push("/")}
          >
            New Translation
          </Button>
        </div>

        {/* Table */}
        {isLoading ? (
          <p className="text-sm text-slate-500">Loading jobs...</p>
        ) : jobs.length === 0 ? (
          /* Empty state */
          <div className="text-center py-16 space-y-3">
            <p className="text-base font-semibold text-slate-700">No translations yet</p>
            <p className="text-sm text-slate-500">Upload a document to get started.</p>
            <Button
              variant="outline"
              className="border-indigo-600 text-indigo-600 hover:bg-indigo-50 mt-2"
              onClick={() => router.push("/")}
            >
              Translate a Document
            </Button>
          </div>
        ) : (
          <JobsTable jobs={jobs} />
        )}
      </main>
    </>
  )
}
