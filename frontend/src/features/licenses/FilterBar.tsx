"use client"

import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { useCallback } from "react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import type { LicenseTier, LicenseStatus } from "@/lib/types"

export interface LicenseFilters {
  tier: LicenseTier | ""
  status: LicenseStatus | ""
  issued_after: string
  issued_before: string
}

interface FilterBarProps {
  filters: LicenseFilters
}

export function FilterBar({ filters }: FilterBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
      // Reset to page 1 on filter change
      params.delete("page")
      router.push(`${pathname}?${params.toString()}`)
    },
    [router, pathname, searchParams]
  )

  function clearAll() {
    const params = new URLSearchParams()
    router.push(pathname)
  }

  const hasFilters =
    filters.tier || filters.status || filters.issued_after || filters.issued_before

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 bg-white rounded-lg border border-zinc-200">
      <div className="flex flex-col gap-1 min-w-[140px]">
        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Tier</label>
        <Select
          value={filters.tier || "all"}
          onValueChange={(v) => update("tier", v === "all" ? "" : v)}
        >
          <SelectTrigger data-testid="filter-tier" className="h-8 text-sm">
            <SelectValue placeholder="All tiers" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tiers</SelectItem>
            <SelectItem value="starter">Starter</SelectItem>
            <SelectItem value="professional">Professional</SelectItem>
            <SelectItem value="enterprise">Enterprise</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1 min-w-[140px]">
        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Status</label>
        <Select
          value={filters.status || "all"}
          onValueChange={(v) => update("status", v === "all" ? "" : v)}
        >
          <SelectTrigger data-testid="filter-status" className="h-8 text-sm">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
            <SelectItem value="revoked">Revoked</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Issued after</label>
        <Input
          data-testid="filter-issued-after"
          type="date"
          className="h-8 text-sm w-[150px]"
          value={filters.issued_after}
          onChange={(e) => update("issued_after", e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Issued before</label>
        <Input
          data-testid="filter-issued-before"
          type="date"
          className="h-8 text-sm w-[150px]"
          value={filters.issued_before}
          onChange={(e) => update("issued_before", e.target.value)}
        />
      </div>

      {hasFilters && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 text-zinc-500 hover:text-zinc-900"
          onClick={clearAll}
          data-testid="filter-clear"
        >
          Clear filters
        </Button>
      )}
    </div>
  )
}
