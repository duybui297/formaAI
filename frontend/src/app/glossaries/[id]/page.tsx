"use client"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft } from "lucide-react"
import { TermsTable } from "@/features/glossary/TermsTable"
import { CSVUploadButton } from "@/features/glossary/CSVUploadButton"
import type { Glossary } from "@/lib/types"

export default function GlossaryDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const {
    data: glossary,
    isLoading,
    refetch,
  } = useQuery<Glossary>({
    queryKey: ["glossary", id],
    queryFn: async () => {
      const res = await fetch(`/api/glossaries/${id}`)
      if (!res.ok) throw new Error("Failed to load glossary")
      // Single-item endpoint returns Glossary directly (no wrapper)
      return res.json()
    },
    enabled: !!id,
  })

  const handleTermsChange = () => {
    refetch()
  }

  const handleImported = () => {
    refetch()
    // Also invalidate the glossary list cache so terms count updates there
    queryClient.invalidateQueries({ queryKey: ["glossaries"] })
  }

  if (isLoading) {
    return (
      <div>
        <div className="px-8 py-8">
          <p className="text-slate-400">Loading…</p>
        </div>
      </div>
    )
  }

  if (!glossary) {
    return (
      <div>
        <div className="px-8 py-8">
          <p className="text-red-500">Glossary not found.</p>
          <Link href="/glossaries" className="text-violet-600 underline mt-2 inline-block">
            ← Back to Glossaries
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/glossaries"
            className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 mb-4"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Glossaries
          </Link>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold font-[--font-montserrat] text-[#111111]">
                {glossary.name}
              </h1>
              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-sm">
                {glossary.source_lang} → {glossary.target_lang}
              </span>
            </div>
            <CSVUploadButton glossaryId={id} onImported={handleImported} />
          </div>
        </div>

        {/* Terms table */}
        <TermsTable
          glossaryId={id}
          terms={glossary.terms ?? []}
          onTermsChange={handleTermsChange}
        />
      </div>
    </div>
  )
}
