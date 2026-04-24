"use client"
import { useQuery } from "@tanstack/react-query"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { Glossary } from "@/lib/types"

// Sentinel value for the "None" option — Radix UI throws at runtime when value=""
const NONE_SENTINEL = "__none__"

interface GlossarySelectProps {
  sourceLang: string
  targetLang: string
  value: string       // glossary_id or "" (empty = none selected)
  onChange: (id: string) => void
}

export function GlossarySelect({ sourceLang, targetLang, value, onChange }: GlossarySelectProps) {
  const enabled = !!sourceLang && !!targetLang && sourceLang !== "auto"

  const { data: glossaries = [], isLoading } = useQuery<Glossary[]>({
    queryKey: ["glossaries", sourceLang, targetLang],
    queryFn: async () => {
      const res = await fetch(
        `/api/glossaries?source_lang=${sourceLang}&target_lang=${targetLang}`
      )
      if (!res.ok) throw new Error("Failed to load glossaries")
      const data = await res.json()
      // API returns {"glossaries": [...]} — must unwrap
      return data.glossaries as Glossary[]
    },
    enabled,
  })

  // Map "" → NONE_SENTINEL for Radix (value="" throws at runtime)
  const selectValue = value || NONE_SENTINEL

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-500 font-[--font-roboto]">Glossary (optional)</label>
      <Select
        value={selectValue}
        onValueChange={(v) => onChange(v === NONE_SENTINEL ? "" : v)}
        disabled={!enabled || isLoading}
      >
        <SelectTrigger className="w-full">
          <SelectValue
            placeholder={
              !enabled
                ? "Select languages first"
                : isLoading
                ? "Loading…"
                : glossaries.length === 0
                ? "No glossary for this pair"
                : "None"
            }
          />
        </SelectTrigger>
        <SelectContent>
          {/* Use NONE_SENTINEL — Radix throws on value="" */}
          <SelectItem value={NONE_SENTINEL}>None</SelectItem>
          {glossaries.map((g) => (
            <SelectItem key={g.id} value={g.id}>
              {g.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {enabled && !isLoading && glossaries.length === 0 && (
        <p className="text-xs text-slate-400">
          No glossaries for this language pair.{" "}
          <a href="/glossaries" className="text-violet-600 underline">
            Create one
          </a>
          .
        </p>
      )}
    </div>
  )
}
