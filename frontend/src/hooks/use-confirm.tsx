"use client"

import * as React from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { buttonVariants } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export type ConfirmTone = "danger" | "warning" | "default"

export interface ConfirmOptions {
  title: string
  description?: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: ConfirmTone
}

interface ConfirmState extends ConfirmOptions {
  open: boolean
  resolve: ((ok: boolean) => void) | null
}

interface ConfirmContextValue {
  confirm: (opts: ConfirmOptions) => Promise<boolean>
}

const ConfirmContext = React.createContext<ConfirmContextValue | null>(null)

export function useConfirm(): ConfirmContextValue["confirm"] {
  const ctx = React.useContext(ConfirmContext)
  if (!ctx) {
    throw new Error("useConfirm must be used within <ConfirmProvider>")
  }
  return ctx.confirm
}

const TONE_BUTTON_CLASS: Record<ConfirmTone, string> = {
  default: buttonVariants(),
  warning: cn(buttonVariants(), "bg-amber-500 hover:bg-amber-600 text-white shadow-sm"),
  danger: buttonVariants({ variant: "destructive" }),
}

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<ConfirmState>({
    open: false,
    title: "",
    resolve: null,
  })

  const confirm = React.useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setState({
        open: true,
        title: opts.title,
        description: opts.description,
        confirmLabel: opts.confirmLabel,
        cancelLabel: opts.cancelLabel,
        tone: opts.tone,
        resolve,
      })
    })
  }, [])

  const close = React.useCallback((ok: boolean) => {
    setState((prev) => {
      prev.resolve?.(ok)
      return { ...prev, open: false, resolve: null }
    })
  }, [])

  const ctx = React.useMemo(() => ({ confirm }), [confirm])

  const tone = state.tone ?? "default"
  const confirmLabel = state.confirmLabel ?? (tone === "default" ? "Confirm" : "Delete")
  const cancelLabel = state.cancelLabel ?? "Cancel"

  return (
    <ConfirmContext.Provider value={ctx}>
      {children}
      <AlertDialog
        open={state.open}
        onOpenChange={(open) => {
          if (!open) close(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{state.title}</AlertDialogTitle>
            {state.description && (
              <AlertDialogDescription>{state.description}</AlertDialogDescription>
            )}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => close(false)}>{cancelLabel}</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                close(true)
              }}
              className={TONE_BUTTON_CLASS[tone]}
            >
              {confirmLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConfirmContext.Provider>
  )
}