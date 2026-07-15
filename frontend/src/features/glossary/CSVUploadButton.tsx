"use client"
import { useRef } from "react"
import { Upload } from "lucide-react"
import { useCrudToast } from "@/hooks/use-crud-toast"
import { Button } from "@/components/ui/button"
import { authFetch } from "@/lib/auth"

interface CSVUploadButtonProps {
  glossaryId: string
  onImported: (count: number) => void
}

export function CSVUploadButton({ glossaryId, onImported }: CSVUploadButtonProps) {
  const crud = useCrudToast()
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const form = new FormData()
    form.append("file", file)

    try {
      const res = await authFetch(`/v1/glossaries/${glossaryId}/terms/import`, {
        method: "POST",
        body: form,
        throwOnError: false,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const msg = data.detail || data.error || "Import failed."
        crud.failed("import", "terms", msg)
        return
      }
      const count = data.imported ?? 0
      crud.imported(
        "Terms",
        `${count} term${count !== 1 ? "s" : ""} from ${file.name}`,
      )
      onImported(count)
    } catch (err) {
      crud.failed("import", "terms", err)
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
