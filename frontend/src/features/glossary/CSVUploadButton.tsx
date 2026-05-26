"use client"
import { useRef } from "react"
import { Upload } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { Button } from "@/components/ui/button"
import { authFetch } from "@/lib/auth"

interface CSVUploadButtonProps {
  glossaryId: string
  onImported: (count: number) => void
}

export function CSVUploadButton({ glossaryId, onImported }: CSVUploadButtonProps) {
  const { toast } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const form = new FormData()
    form.append("file", file)

    try {
      const res = await authFetch(`/glossaries/${glossaryId}/terms/import`, {
        method: "POST",
        body: form,
        throwOnError: false,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = data.detail || data.error || "Import failed."
        toast({ variant: "destructive", description: `Import failed: ${msg}` })
        return
      }
      const count = data.imported ?? 0
      toast({ description: `Imported ${count} term${count !== 1 ? "s" : ""}.` })
      onImported(count)
    } catch {
      toast({ variant: "destructive", description: "Network error during import." })
    } finally {
      // Reset so same file can be re-imported
      e.target.value = ""
    }
  }

  return (
    <>
      <Button
        variant="outline"
        onClick={() => inputRef.current?.click()}
        className="flex items-center gap-2"
      >
        <Upload className="h-4 w-4" />
        Import CSV
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleFileChange}
      />
    </>
  )
}
