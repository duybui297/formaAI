"use client"

import { useState, Suspense } from "react"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { Plus, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { listLicenses } from "@/lib/api"
import { LicensesTable } from "@/features/licenses/LicensesTable"
import { FilterBar } from "@/features/licenses/FilterBar"
import { BulkActionsBar } from "@/features/licenses/BulkActionsBar"
import { CreateLicenseDialog } from "@/features/licenses/CreateLicenseDialog"
import { OneTimeKeyDialog } from "@/features/licenses/OneTimeKeyDialog"
import { LicenseDetailDrawer } from "@/features/licenses/LicenseDetailDrawer"
import type {
  License,
  LicenseTier,
  LicenseStatus,
  LicensesListParams,
} from "@/lib/types"
import type { SortField, SortDir } from "@/features/licenses/LicensesTable"

const PAGE_SIZE = 20

function LicensesPageInner() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  // Derive filters from URL
  const tier = (searchParams.get("tier") ?? "") as LicenseTier | ""
  const status = (searchParams.get("status") ?? "") as LicenseStatus | ""
  const issued_after = searchParams.get("issued_after") ?? ""
  const issued_before = searchParams.get("issued_before") ?? ""
  const page = Number(searchParams.get("page") ?? "1")
  const sortBy = (searchParams.get("sort_by") ?? null) as SortField | null
  const sortDir = (searchParams.get("sort_dir") ?? "desc") as SortDir

  // Local UI state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [createOpen, setCreateOpen] = useState(false)
  const [rawKey, setRawKey] = useState<string | null>(null)
  const [detailLicense, setDetailLicense] = useState<License | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const queryParams: LicensesListParams = {
    page,
    page_size: PAGE_SIZE,
    ...(tier ? { tier } : {}),
    ...(status ? { status } : {}),
    ...(issued_after ? { issued_after } : {}),
    ...(issued_before ? { issued_before } : {}),
    ...(sortBy ? { sort_by: sortBy, sort_dir: sortDir } : {}),
  }

  const { data, isLoading } = useQuery({
    queryKey: ["licenses", queryParams],
    queryFn: () => listLicenses(queryParams),
  })

  const licenses = data?.licenses ?? []
  const total = data?.total ?? 0

  function updateSort(field: SortField) {
    const params = new URLSearchParams(searchParams.toString())
    if (sortBy === field) {
      params.set("sort_dir", sortDir === "asc" ? "desc" : "asc")
    } else {
      params.set("sort_by", field)
      params.set("sort_dir", "asc")
    }
    params.delete("page")
    router.push(`${pathname}?${params.toString()}`)
  }

  function updatePage(newPage: number) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", String(newPage))
    router.push(`${pathname}?${params.toString()}`)
  }

  function handleSelectId(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function handleSelectAll(checked: boolean) {
    if (checked) {
      setSelectedIds(new Set(licenses.map((l) => l.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  function handleRowClick(license: License) {
    setDetailLicense(license)
    setDetailOpen(true)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-5 border-b border-border bg-card flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-primary" />
          <h1 className="text-xl font-bold font-montserrat text-foreground">
            License Management
          </h1>
        </div>
        <Button
          data-testid="create-license-button"
          onClick={() => setCreateOpen(true)}
          className="gap-1.5"
        >
          <Plus className="w-4 h-4" />
          Create License
        </Button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <FilterBar
          filters={{ tier, status, issued_after, issued_before }}
        />

        {selectedIds.size > 0 && (
          <BulkActionsBar
            selectedIds={selectedIds}
            onClearSelection={() => setSelectedIds(new Set())}
          />
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <span className="text-sm text-muted-foreground">Loading…</span>
          </div>
        ) : (
          <LicensesTable
            licenses={licenses}
            total={total}
            page={page}
            pageSize={PAGE_SIZE}
            sortBy={sortBy}
            sortDir={sortDir}
            selectedIds={selectedIds}
            onSort={updateSort}
            onPageChange={updatePage}
            onSelectId={handleSelectId}
            onSelectAll={handleSelectAll}
            onRowClick={handleRowClick}
          />
        )}
      </div>

      {/* Dialogs */}
      <CreateLicenseDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(key) => {
          setRawKey(key)
        }}
      />

      <OneTimeKeyDialog
        open={rawKey !== null}
        rawKey={rawKey ?? ""}
        onClose={() => setRawKey(null)}
      />

      <LicenseDetailDrawer
        license={detailLicense}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </div>
  )
}

export default function LicensesPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
      <LicensesPageInner />
    </Suspense>
  )
}
