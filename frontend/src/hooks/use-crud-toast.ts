"use client"

import { useToast } from "@/hooks/use-toast"

type CrudAction =
  | "create"
  | "update"
  | "edit"
  | "delete"
  | "remove"
  | "save"
  | "send"
  | "revoke"
  | "suspend"
  | "extend"
  | "invite"
  | "copy"
  | "import"
  | "apply"
  | "remove"

interface CrudToast {
  created: (entity: string, identifier?: string) => void
  updated: (entity: string, identifier?: string) => void
  deleted: (entity: string, identifier?: string) => void
  sent: (entity: string, identifier?: string) => void
  revoked: (entity: string, identifier?: string) => void
  suspended: (entity: string, identifier?: string) => void
  extended: (entity: string, identifier?: string) => void
  imported: (entity: string, identifier?: string) => void
  info: (title: string, description?: string) => void
  failed: (action: CrudAction, entity: string, err: unknown) => void
}

function messageOf(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === "string") return err
  return "Something went wrong. Please try again."
}

export function useCrudToast(): CrudToast {
  const { toast } = useToast()

  const success = (title: string, description?: string) =>
    toast({
      variant: "success",
      title,
      description,
    })

  return {
    created: (entity, identifier) => success(`${entity} created`, identifier),
    updated: (entity, identifier) => success(`${entity} updated`, identifier),
    deleted: (entity, identifier) => success(`${entity} deleted`, identifier),
    sent: (entity, identifier) => success(`${entity} sent`, identifier),
    revoked: (entity, identifier) => success(`${entity} revoked`, identifier),
    suspended: (entity, identifier) => success(`${entity} suspended`, identifier),
    extended: (entity, identifier) => success(`${entity} extended`, identifier),
    imported: (entity, identifier) => success(`${entity} imported`, identifier),
    info: (title, description) =>
      toast({ variant: "info", title, description }),
    failed: (action, entity, err) =>
      toast({
        variant: "destructive",
        title: `Failed to ${action} ${entity}`,
        description: messageOf(err),
      }),
  }
}
