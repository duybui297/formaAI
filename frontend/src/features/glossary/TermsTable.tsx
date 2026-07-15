"use client"
import { useState } from "react"
import { Pencil, Trash2, Check, X } from "lucide-react"
import { useCrudToast } from "@/hooks/use-crud-toast"
import { useConfirm } from "@/hooks/use-confirm"
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
import { authFetch } from "@/lib/auth"
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
  const crud = useCrudToast()
  const [sourceTerm, setSourceTerm] = useState("")
  const [targetTerm, setTargetTerm] = useState("")
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)

  const canAdd = sourceTerm.trim().length > 0 && targetTerm.trim().length > 0

  const handleAdd = async () => {
    if (!canAdd) return
    setSaving(true)
    try {
      const res = await authFetch(`/v1/glossaries/${glossaryId}/terms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_term: sourceTerm.trim(),
          target_term: targetTerm.trim(),
          notes: notes.trim() || null,
        }),
        throwOnError: false,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        crud.failed("create", "term", data.detail || "Failed to add term.")
        return
      }
      setSourceTerm("")
      setTargetTerm("")
      setNotes("")
      crud.created("Term", sourceTerm.trim())
      onAdded()
    } catch (err) {
      crud.failed("create", "term", err)
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
  const crud = useCrudToast()
  const confirm = useConfirm()
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
      const res = await authFetch(`/v1/glossaries/${glossaryId}/terms/${termId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_term: editState.source_term.trim(),
          target_term: editState.target_term.trim(),
          notes: editState.notes.trim() || null,
        }),
        throwOnError: false,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        crud.failed("update", "term", data.detail || "Failed to save term.")
        return
      }
      setEditingId(null)
      crud.updated("Term", editState.source_term.trim())
      onTermsChange()
    } catch (err) {
      crud.failed("update", "term", err)
    }
  }

  const deleteTerm = async (termId: string, sourceTerm: string) => {
    const ok = await confirm({
      title: "Delete term?",
      description: (
        <>
          This will permanently delete <strong>{sourceTerm}</strong>. This cannot be undone.
        </>
      ),
      confirmLabel: "Delete",
      tone: "danger",
    })
    if (!ok) return
    try {
      const res = await authFetch(`/v1/glossaries/${glossaryId}/terms/${termId}`, {
        method: "DELETE",
        throwOnError: false,
      })
      if (!res.ok) {
        crud.failed("delete", "term", "Failed to delete term.")
        return
      }
      crud.deleted("Term", sourceTerm)
      onTermsChange()
    } catch (err) {
      crud.failed("delete", "term", err)
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
                    <X className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ) : (
            <TableRow key={term.id}>
              <TableCell className="text-sm">{term.source_term}</TableCell>
              <TableCell className="text-sm">{term.target_term}</TableCell>
              <TableCell className="text-sm text-muted-foreground">{term.notes ?? "—"}</TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => startEdit(term)}
                    aria-label={`Edit term ${term.source_term}`}
                  >
                    <Pencil className="h-4 w-4 text-muted-foreground" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteTerm(term.id, term.source_term)}
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
