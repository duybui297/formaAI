"use client"
import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GlossaryList } from "@/features/glossary/GlossaryList"
import { GlossaryCreateDialog } from "@/features/glossary/GlossaryCreateDialog"
import { authFetch } from "@/lib/auth"
import type { Glossary } from "@/lib/types"

export default function GlossariesPage() {
  const [createOpen, setCreateOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: glossaries = [], isLoading } = useQuery<Glossary[]>({
    queryKey: ["glossaries"],
    queryFn: async () => {
      const res = await authFetch("/glossaries", { throwOnError: false })
      if (!res.ok) {
        if (res.status === 401) {
          return [] as Glossary[]
        }
        throw new Error(`Failed to load glossaries: ${res.status}`)
      }
      const d = await res.json()
      return (d.glossaries ?? []) as Glossary[]
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      authFetch(`/glossaries/${id}`, { method: "DELETE", throwOnError: false }).then((r) => {
        if (!r.ok) throw new Error("Delete failed")
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["glossaries"] }),
  })

  return (
    <div>
      <div className="px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold font-[--font-montserrat] text-[#111111]">
            Glossaries
          </h1>
          <Button
            onClick={() => setCreateOpen(true)}
            className="bg-violet-500 hover:bg-violet-600 text-white"
          >
            <Plus className="h-4 w-4 mr-2" />
            Create Glossary
          </Button>
        </div>

        {isLoading ? (
          <p className="text-slate-400">Loading…</p>
        ) : (
          <GlossaryList
            glossaries={glossaries}
            onDelete={(id) => deleteMutation.mutate(id)}
          />
        )}

        <GlossaryCreateDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["glossaries"] })
            setCreateOpen(false)
          }}
        />
      </div>
    </div>
  )
}
