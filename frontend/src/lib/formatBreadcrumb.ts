/**
 * Format a structural_position string into a human-readable breadcrumb string.
 *
 * Detection is prefix-based — no format parameter needed:
 *   "slide." or "master." → PPTX
 *   "page."               → PDF
 *   anything else         → DOCX or raw fallback
 *
 * D-03-07: Breadcrumb badge rendered above source text in SegmentRow.
 * UI-SPEC: ALL indices displayed 1-based (storage is 0-based).
 * Never throws — returns raw string if pattern does not match.
 */

/** Convert a 0-based index string to a 1-based display string. Non-numeric → "?". */
function _oneBased(raw: string | undefined): string {
  if (raw === undefined) return "?"
  const n = Number(raw)
  return Number.isFinite(n) ? String(n + 1) : "?"
}

export function formatBreadcrumb(structuralPosition: string): string {
  if (!structuralPosition) return structuralPosition

  if (structuralPosition.startsWith("slide.") || structuralPosition.startsWith("master.")) {
    return _formatPptx(structuralPosition)
  }
  if (structuralPosition.startsWith("page.")) {
    return _formatPdf(structuralPosition)
  }
  // DOCX or unknown — return raw (safe fallback)
  return structuralPosition
}

/**
 * PPTX structural_position patterns (storage 0-based, display 1-based):
 *   slide.N.shape.M.tf.P.para.K  → "Slide (N+1) / Shape (M+1) / ¶(K+1)"
 *   slide.N.notes.para.K         → "Slide (N+1) / Notes / ¶(K+1)"
 *   slide.N.shape.M.smartart     → "Slide (N+1) / Shape (M+1) / SmartArt"
 *   master.N.shape.M.para.K      → "Master (N+1) / Shape (M+1) / ¶(K+1)"
 */
function _formatPptx(pos: string): string {
  const parts = pos.split(".")

  // master.N.shape.M.para.K
  if (parts[0] === "master") {
    const masterNum = _oneBased(parts[1])
    const shapeIdx = parts.indexOf("shape")
    const shapeNum = shapeIdx !== -1 ? _oneBased(parts[shapeIdx + 1]) : "?"
    const paraIdx = parts.indexOf("para")
    const paraNum = paraIdx !== -1 ? _oneBased(parts[paraIdx + 1]) : "?"
    return `Master ${masterNum} / Shape ${shapeNum} / ¶${paraNum}`
  }

  // slide.N...
  const slideNum = _oneBased(parts[1])

  // slide.N.notes.para.K
  if (parts.includes("notes")) {
    const paraIdx = parts.indexOf("para")
    const paraNum = paraIdx !== -1 ? _oneBased(parts[paraIdx + 1]) : "?"
    return `Slide ${slideNum} / Notes / ¶${paraNum}`
  }

  // slide.N.shape.M.smartart
  if (pos.includes(".smartart")) {
    const shapeIdx = parts.indexOf("shape")
    const shapeNum = shapeIdx !== -1 ? _oneBased(parts[shapeIdx + 1]) : "?"
    return `Slide ${slideNum} / Shape ${shapeNum} / SmartArt`
  }

  // slide.N.shape.M[.group.shape.S].tf.P.para.K
  // Find the last "shape" index (for nested groups)
  let lastShapePos = -1
  for (let i = parts.length - 1; i >= 0; i--) {
    if (parts[i] === "shape") {
      lastShapePos = i
      break
    }
  }
  const shapeNum = lastShapePos !== -1 ? _oneBased(parts[lastShapePos + 1]) : "?"
  const paraIdx = parts.lastIndexOf("para")
  const paraNum = paraIdx !== -1 ? _oneBased(parts[paraIdx + 1]) : "?"

  return `Slide ${slideNum} / Shape ${shapeNum} / ¶${paraNum}`
}

/**
 * PDF structural_position patterns (storage 0-based, display 1-based):
 *   page.N.col.C.block.B.*  → "Page (N+1) / Col (C+1) / Block (B+1)"
 *   page.N.block.B.*        → "Page (N+1) / Block (B+1)"
 */
function _formatPdf(pos: string): string {
  const parts = pos.split(".")
  const pageNum = _oneBased(parts[1])

  if (parts.includes("col")) {
    const colIdx = parts.indexOf("col")
    const colNum = _oneBased(parts[colIdx + 1])
    const blockIdx = parts.indexOf("block")
    const blockNum = blockIdx !== -1 ? _oneBased(parts[blockIdx + 1]) : "?"
    return `Page ${pageNum} / Col ${colNum} / Block ${blockNum}`
  } else {
    const blockIdx = parts.indexOf("block")
    const blockNum = blockIdx !== -1 ? _oneBased(parts[blockIdx + 1]) : "?"
    return `Page ${pageNum} / Block ${blockNum}`
  }
}
