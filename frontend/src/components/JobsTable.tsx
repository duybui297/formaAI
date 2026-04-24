"use client"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "@/components/StatusBadge"
import type { JobSummary } from "@/lib/types"

function formatAge(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return "just now"
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  return `${Math.floor(diffH / 24)}d ago`
}

function sourceLangDisplay(job: JobSummary): string {
  return job.source_lang === "auto" ? "Auto" : job.source_lang
}

interface JobsTableProps {
  jobs: JobSummary[]
}

export function JobsTable({ jobs }: JobsTableProps) {
  const router = useRouter()

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8 text-xs">#</TableHead>
          <TableHead className="text-xs">Filename</TableHead>
          <TableHead className="text-xs">Languages</TableHead>
          <TableHead className="text-xs">Format</TableHead>
          <TableHead className="text-xs">Status</TableHead>
          <TableHead className="text-xs">Created</TableHead>
          <TableHead className="text-xs text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job, idx) => (
          <TableRow
            key={job.id}
            className="hover:bg-slate-50 cursor-pointer"
            onClick={() => router.push(`/jobs/${job.id}`)}
          >
            <TableCell className="text-xs text-slate-400 font-mono">
              {idx + 1}
            </TableCell>
            <TableCell className="text-sm text-slate-800 max-w-[200px] truncate">
              {job.original_filename}
            </TableCell>
            <TableCell className="text-xs text-slate-600">
              {sourceLangDisplay(job)} → {job.target_lang}
            </TableCell>
            <TableCell>
              <Badge variant="outline" className="text-xs text-slate-700">
                {job.input_format.toUpperCase()}
              </Badge>
            </TableCell>
            <TableCell>
              <StatusBadge status={job.status} />
            </TableCell>
            <TableCell className="text-xs text-slate-500">
              {formatAge(job.created_at)}
            </TableCell>
            <TableCell
              className="text-right"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-end gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  asChild
                >
                  <Link href={`/jobs/${job.id}`}>View</Link>
                </Button>
                {job.status === "done" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs text-indigo-600 hover:text-indigo-700"
                    onClick={() => {
                      window.location.href = `/api/jobs/${job.id}/download`
                    }}
                  >
                    Download
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
