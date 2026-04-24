import { NavBar } from "@/components/NavBar"
import { UploadForm } from "@/components/UploadForm"

export default function UploadPage() {
  return (
    <>
      <NavBar />
      <main className="max-w-3xl mx-auto px-8 py-12">
        <h1 className="text-[20px] font-semibold mb-1">Translate a Document</h1>
        <p className="text-sm text-slate-500 mb-8">
          Upload a DOCX file &mdash; select languages &mdash; download the translated version.
        </p>
        <UploadForm />
      </main>
      <footer className="h-10 flex items-center justify-center text-xs text-slate-400">
        AI Translation &middot; v0.1
      </footer>
    </>
  )
}
