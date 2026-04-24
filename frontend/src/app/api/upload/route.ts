export async function POST(request: Request) {
  const formData = await request.formData()
  const file = formData.get("file") as File | null
  if (!file) {
    return Response.json({ error: "No file provided" }, { status: 400 })
  }

  const backendUrl = process.env.BACKEND_URL || "http://api:8000"
  const backendForm = new FormData()
  backendForm.append("file", file)
  backendForm.append("source_lang", (formData.get("source_lang") as string) || "auto")
  backendForm.append("target_lang", (formData.get("target_lang") as string) || "")
  const trackedAction = formData.get("tracked_changes_action")
  if (trackedAction) {
    backendForm.append("tracked_changes_action", trackedAction as string)
  }

  try {
    const response = await fetch(`${backendUrl}/upload`, {
      method: "POST",
      body: backendForm,
    })
    const data = await response.json()
    return Response.json(data, { status: response.status })
  } catch {
    return Response.json(
      { error: "Backend unavailable. Please try again." },
      { status: 503 }
    )
  }
}
