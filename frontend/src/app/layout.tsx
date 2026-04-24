import type { Metadata } from "next"
import { Inter, Roboto, Montserrat, PT_Mono } from "next/font/google"
import "./globals.css"
import { QueryProvider } from "@/components/providers/query-provider"
import { Toaster } from "@/components/ui/toaster"

// Inter with latin + vietnamese subsets for diacritics (UI-SPEC typography)
const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-inter",
})

// Paper skill fonts (D-02-27/28)
const roboto = Roboto({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-roboto",
})

const montserrat = Montserrat({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-montserrat",
})

const ptMono = PT_Mono({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-pt-mono",
})

export const metadata: Metadata = {
  title: "AI Translation",
  description: "Translate documents with format fidelity",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${roboto.variable} ${montserrat.variable} ${ptMono.variable}`}>
      <body className={`${inter.variable} font-sans antialiased`}>
        <QueryProvider>{children}</QueryProvider>
        <Toaster />
      </body>
    </html>
  )
}
