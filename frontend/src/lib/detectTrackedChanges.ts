import JSZip from "jszip"

/**
 * B4 Option A: Read DOCX bytes client-side and check word/document.xml
 * for <w:ins> / <w:del> elements (tracked changes markers).
 * Called on file selection — BEFORE any upload — so the modal can be shown
 * before the first POST fires.
 * Returns false for non-.docx files or malformed zip (server handles validation).
 */
export async function detectTrackedChanges(file: File): Promise<boolean> {
  if (!file.name.toLowerCase().endsWith(".docx")) return false
  try {
    const arrayBuffer = await file.arrayBuffer()
    const zip = await JSZip.loadAsync(arrayBuffer)
    const docXml = await zip.file("word/document.xml")?.async("string")
    if (!docXml) return false
    return docXml.includes("<w:ins") || docXml.includes("<w:del")
  } catch {
    // Malformed DOCX or zip read error — let the server validate
    return false
  }
}
