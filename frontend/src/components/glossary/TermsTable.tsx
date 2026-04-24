"use client"
import { useState } from "react"
import { Pencil, Trash2, Check, X } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { GlossaryTerm } from "@/lib/types"

interface TermsTableProps {
  glossaryId: string
  terms: GlossaryTerm[]
  onTermsChange: () => void  // triggers parent refetch
}

interface EditState {
  source_term: string
  target_term: string
  notes: string
}

function TermAddRow({
  glossaryId,
  onAdded,
}: {
  glossaryId: string
  onAdded: () => void
}) {
  const { toast } = useToast()
  const [sourceTerm, setSourceTerm] = useState("")
  const [targetTerm, setTargetTerm] = useState("")
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)

  const canAdd = sourceTerm.trim().length > 0 && targetTerm.trim().length > 0

  const handleAdd = async () => {
    if (!canAdd) return
    setSaving(true)
    try {
      const res = await fetch(`/api/glossaries/${glossaryId}/terms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_term: sourceTerm.trim(),
          target_term: targetTerm.trim(),
          notes: notes.trim() || null,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast({ variant: "destructive", description: data.detail || "Failed to add term." })
        return
      }
      setSourceTerm("")
      setTargetTerm("")
      setNotes("")
      onAdded()
    } catch {
      toast({ variant: "destructive", description: "Network error. Please try again." })
    } finally {
      setSaving(false)
    }
  }

  return (
    <TableRow>
      <TableCell>
        <Input
          value={sourceTerm}
          onChange={(e) => setSourceTerm(e.target.value)}
          placeholder="Source term"
          className="h-8 text-sm"
        />
      </TableCell>
      <TableCell>
        <Input
          value={targetTerm}
          onChange={(e) => setTargetTerm(e.target.value)}
          placeholder="Target term"
          className="h-8 text-sm"
        />
      </TableCell>
      <TableCell>
        <Input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes (optional)"
          className="h-8 text-sm"
        />
      </TableCell>
      <TableCell>
        <Button
          size="sm"
          disabled={!canAdd || saving}
          onClick={handleAdd}
          className="bg-violet-500 hover:bg-violet-600 text-white h-8"
        >
          {saving ? "Adding…" : "Add Term"}
        </Button>
      </TableCell>
    </TableRow>
  )
}

export function TermsTable({ glossaryId, terms, onTermsChange }: TermsTableProps) {
  const { toast } = useToast()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editState, setEditState] = useState<EditState>({ source_term: "", target_term: "", notes: "" })

  const startEdit = (term: GlossaryTerm) => {
    setEditingId(term.id)
    setEditState({
      source_term: term.source_term,
      target_term: term.target_term,
      notes: term.notes ?? "",
    })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditState({ source_term: "", target_term: "", notes: "" })
  }

  const saveEdit = async (termId: string) => {
    try {
      const res = await fetch(`/api/glossaries/${glossaryId}/terms/${termId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_term: editState.source_term.trim(),
          target_term: editState.target_term.trim(),
          notes: editState.notes.trim() || null,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        toast({ variant: "destructive", description: data.detail || "Failed to save term." })
        return
      }
      setEditingId(null)
      onTermsChange()
    } catch {
      toast({ variant: "destructive", description: "Network error. Please try again." })
    }
  }

  const deleteTerm = async (termId: string) => {
    try {
      const res = await fetch(`/api/glossaries/${glossaryId}/terms/${termId}`, {
        method: "DELETE",
      })
      if (!res.ok) {
        toast({ variant: "destructive", description: "Failed to delete term." })
        return
      }
      onTermsChange()
    } catch {
      toast({ variant: "destructive", description: "Network error. Please try again." })
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Source Term</TableHead>
          <TableHead>Target Term</TableHead>
          <TableHead>Notes</TableHead>
          <TableHead className="w-28">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {terms.map((term) =>
          editingId === term.id ? (
            <TableRow key={term.id}>
              <TableCell>
                <Input
                  value={editState.source_term}
                  onChange={(e) =>
                    setEditState((s) => ({ ...s, source_term: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </TableCell>
              <TableCell>
                <Input
                  value={editState.target_term}
                  onChange={(e) =>
                    setEditState((s) => ({ ...s, target_term: e.target.value }))
                  }
                  className="h-8 text-sm"
                />
              </TableCell>
              <TableCell>
                <Input
                  value={editState.notes}
                  onChange={(e) =>
                    setEditState((s) => ({ ...s, notes: e.target.value }))
                  }
                  placeholder="Notes (optional)"
                  className="h-8 text-sm"
                />
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => saveEdit(term.id)}
                    aria-label="Save"
                  >
                    <Check className="h-4 w-4 text-emerald-600" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={cancelEdit}
                    aria-label="Cancel"
                  >
                    <X className="h-4 w-4 text-slate-500" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            <TableRow key={term.id}>
              <TableCell className="text-sm">{term.source_term}</TableCell>
              <TableCell className="text-sm">{term.target_term}</TableCell>
              <TableCell className="text-sm text-slate-500">{term.notes ?? "—"}</TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => startEdit(term)}
                    aria-label={`Edit term ${term.source_term}`}
                  >
                    <Pencil className="h-4 w-4 text-slate-500" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteTerm(term.id)}
                    aria-label={`Delete term ${term.source_term}`}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          )
        )}
        {/* Always-visible add row at bottom */}
        <TermAddRow glossaryId={glossaryId} onAdded={onTermsChange} />
      </TableBody>
    </Table>
  )
}
