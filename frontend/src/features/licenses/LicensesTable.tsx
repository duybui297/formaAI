"use client"

import { useState } from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react"
import type { License, LicenseTier, LicenseStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

// ---- Badge helpers ----

const TIER_CLASSES: Record<LicenseTier, string> = {
  starter: "bg-sky-100 text-sky-800 border-sky-200",
  professional: "bg-violet-100 text-violet-800 border-violet-200",
  enterprise: "bg-amber-100 text-amber-800 border-amber-200",
}

const STATUS_CLASSES: Record<LicenseStatus, string> = {
  pending: "bg-blue-100 text-blue-800 border-blue-200",
  active: "bg-emerald-100 text-emerald-800 border-emerald-200",
  suspended: "bg-orange-100 text-orange-800 border-orange-200",
  revoked: "bg-red-100 text-red-800 border-red-200",
  expired: "bg-muted text-muted-foreground border-border",
}

function TierBadge({ tier }: { tier: LicenseTier }) {
  return (
    <span
      data-testid="tier-badge"
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border",
        TIER_CLASSES[tier]
      )}
    >
      {tier.charAt(0).toUpperCase() + tier.slice(1)}
    </span>
  )
}

function StatusChip({ status }: { status: LicenseStatus }) {
  return (
    <span
      data-testid="status-chip"
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border",
        STATUS_CLASSES[status]
      )}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// ---- Column sort ----

export type SortField = "issued_at" | "expired_at" | "tier" | "status" | "customer_id"
export type SortDir = "asc" | "desc"

interface SortHeaderProps {
  field: SortField
  label: string
  sortBy: SortField | null
  sortDir: SortDir
  onSort: (field: SortField) => void
}

function SortHeader({ field, label, sortBy, sortDir, onSort }: SortHeaderProps) {
  const active = sortBy === field
  return (
    <button
      data-testid={`sort-${field}`}
      className="flex items-center gap-1 hover:text-foreground font-medium text-xs uppercase tracking-wide text-muted-foreground"
      onClick={() => onSort(field)}
      type="button"
    >
      {label}
      {active ? (
        sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
      ) : (
        <ChevronsUpDown className="w-3 h-3 opacity-40" />
      )}
    </button>
  )
}

// ---- Table ----

interface LicensesTableProps {
  licenses: License[]
  total: number
  page: number
  pageSize: number
  sortBy: SortField | null
  sortDir: SortDir
  selectedIds: Set<string>
  onSort: (field: SortField) => void
  onPageChange: (page: number) => void
  onSelectId: (id: string, checked: boolean) => void
  onSelectAll: (checked: boolean) => void
  onRowClick: (license: License) => void
}

export function LicensesTable({
  licenses,
  total,
  page,
  pageSize,
  sortBy,
  sortDir,
  selectedIds,
  onSort,
  onPageChange,
  onSelectId,
  onSelectAll,
  onRowClick,
}: LicensesTableProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const allSelected = licenses.length > 0 && licenses.every((l) => selectedIds.has(l.id))

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted">
              <TableHead className="w-10">
                <Checkbox
                  data-testid="select-all"
                  checked={allSelected}
                  onChange={(e) => onSelectAll(e.target.checked)}
                  aria-label="Select all"
                />
              </TableHead>
              <TableHead>
                <SortHeader field="customer_id" label="Key / Customer" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              </TableHead>
              <TableHead>
                <SortHeader field="tier" label="Tier" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              </TableHead>
              <TableHead>
                <SortHeader field="status" label="Status" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              </TableHead>
              <TableHead>
                <SortHeader field="issued_at" label="Issued" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              </TableHead>
              <TableHead>
                <SortHeader field="expired_at" label="Expires" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {licenses.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-12 text-sm">
                  No licenses found.
                </TableCell>
              </TableRow>
            ) : (
              licenses.map((license) => (
                <TableRow
                  key={license.id}
                  data-testid="license-row"
                  className="cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => onRowClick(license)}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      data-testid={`select-${license.id}`}
                      checked={selectedIds.has(license.id)}
                      onChange={(e) => onSelectId(license.id, e.target.checked)}
                      aria-label={`Select license ${license.key_masked}`}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span
                        data-testid="masked-key"
                        className="font-mono text-sm text-foreground tracking-wide"
                      >
                        {license.key_masked}
                      </span>
                      {license.customer_id && (
                        <span className="text-xs text-muted-foreground">{license.customer_id}</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <TierBadge tier={license.tier} />
                  </TableCell>
                  <TableCell>
                    <StatusChip status={license.status} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(license.issued_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {license.expired_at
                      ? new Date(license.expired_at).toLocaleDateString()
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {total === 0
            ? "No results"
            : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            data-testid="page-prev"
          >
            Previous
          </Button>
          <span className="text-xs">
            Page {page} / {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
            data-testid="page-next"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
