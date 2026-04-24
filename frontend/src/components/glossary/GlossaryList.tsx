"use client"
import Link from "next/link"
import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { Glossary } from "@/lib/types"

interface GlossaryListProps {
  glossaries: Glossary[]
  onDelete: (id: string) => void
}

export function GlossaryList({ glossaries, onDelete }: GlossaryListProps) {
  if (glossaries.length === 0) {
    return (
      <p className="text-slate-400 text-sm py-8 text-center">
        No glossaries yet. Create one to get started.
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Language Pair</TableHead>
          <TableHead>Terms</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="w-16">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {glossaries.map((g) => (
          <TableRow key={g.id}>
            <TableCell>
              <Link
                href={`/glossaries/${g.id}`}
                className="text-violet-600 hover:underline font-medium"
              >
                {g.name}
              </Link>
            </TableCell>
            <TableCell className="text-slate-600">
              {g.source_lang} → {g.target_lang}
            </TableCell>
            <TableCell className="text-slate-600">
              {g.terms?.length ?? "—"}
            </TableCell>
            <TableCell className="text-slate-500 text-sm">
              {new Date(g.created_at).toLocaleDateString()}
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  if (window.confirm("Delete glossary and all its terms?")) {
                    onDelete(g.id)
                  }
                }}
                aria-label={`Delete glossary ${g.name}`}
              >
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
