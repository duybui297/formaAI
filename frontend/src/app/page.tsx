import { redirect } from "next/navigation"

// Root page redirects to the upload form (implemented in Plan 01-08)
export default function HomePage() {
  redirect("/upload")
}
