"use client"
import { useQuery } from "@tanstack/react-query"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { getLanguages } from "@/lib/api"
import type { Language } from "@/lib/types"

// B5: priority codes match SUPPORTED_LANGUAGES code keys in Plan 06a
const PRIORITY_CODES = ["vi", "en", "ja", "zh", "zh-tw"]

interface LanguageSelectProps {
  value: string           // language code (e.g. "vi", "en", "auto")
  onValueChange: (code: string) => void
  includeAutoDetect?: boolean
  placeholder?: string
  label: string
  disabled?: boolean
}

export function LanguageSelect({
  value,
  onValueChange,
  includeAutoDetect = false,
  placeholder,
  label,
  disabled,
}: LanguageSelectProps) {
  const { data: languages = [] } = useQuery<Language[]>({
    queryKey: ["languages"],
    queryFn: getLanguages,
    staleTime: 24 * 60 * 60 * 1000, // 24h — static per model version (UI-SPEC)
  })

  // Exclude "auto" from the groupable list; it's rendered separately when includeAutoDetect=true
  const nonAuto = languages.filter(l => l.code !== "auto")
  const priorityLangs = nonAuto.filter(l => PRIORITY_CODES.includes(l.code))
  const otherLangs = nonAuto
    .filter(l => !PRIORITY_CODES.includes(l.code))
    .sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm text-slate-700">{label}</label>
      <Select value={value} onValueChange={onValueChange} disabled={disabled}>
        <SelectTrigger className="min-h-[48px]">
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent>
          {includeAutoDetect && (
            <SelectItem value="auto">Auto-detect</SelectItem>
          )}
          {priorityLangs.length > 0 && (
            <SelectGroup>
              <SelectLabel>Recommended</SelectLabel>
              {priorityLangs.map(lang => (
                <SelectItem key={lang.code} value={lang.code}>
                  {lang.name}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
          {otherLangs.length > 0 && (
            <SelectGroup>
              <SelectLabel>All Languages</SelectLabel>
              {otherLangs.map(lang => (
                <SelectItem key={lang.code} value={lang.code}>
                  {lang.name}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
        </SelectContent>
      </Select>
    </div>
  )
}
