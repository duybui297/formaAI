"use client"
import Link from "next/link"
import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useConfirm } from "@/hooks/use-confirm"
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
  /**
   * Called only after the user confirms the destructive action.
   * Parent performs the actual delete (typically a mutation).
   */
  onDelete: (id: string) => void | Promise<void>
}

export function GlossaryList({ glossaries, onDelete }: GlossaryListProps) {
  const confirm = useConfirm()

  if (glossaries.length === 0) {
    return (
      <p className="text-muted-foreground text-sm py-8 text-center">
        No glossaries yet. Create one to get started.
      </p>
    )
  }

  const handleDelete = async (g: Glossary) => {
    const ok = await confirm({
      title: "Delete glossary?",
      description: (
        <>
          This will permanently delete <strong>{g.name}</strong> and all of its terms. This cannot be undone.
        </>
      ),
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (ok) await onDelete(g.id)
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
            <TableCell className="text-muted-foreground">
              {g.source_lang} → {g.target_lang}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {g.term_count}
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
              {new Date(g.created_at).toLocaleDateString()}
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleDelete(g)}
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
