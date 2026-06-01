"use client"

import { useState, Suspense } from "react"
import { useSearchParams, useRouter, usePathname } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, Users } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useToast } from "@/hooks/use-toast"
import { getMeApi } from "@/lib/auth"
import { listUsers, createUser, updateUser, deleteUser } from "@/lib/api"
import type {
  AdminUser,
  AdminUsersListParams,
  CreateAdminUserRequest,
} from "@/lib/types"
import type { AuthUser } from "@/lib/auth"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 20

// ---- Badge helpers ----

function RoleBadge({ isSuperuser }: { isSuperuser: boolean }) {
  return (
    <span
      data-testid="role-badge"
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border",
        isSuperuser
          ? "bg-violet-100 text-violet-800 border-violet-200"
          : "bg-zinc-100 text-zinc-600 border-zinc-200"
      )}
    >
      {isSuperuser ? "Admin" : "User"}
    </span>
  )
}

function ActiveChip({ isActive }: { isActive: boolean }) {
  return (
    <span
      data-testid="active-chip"
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border",
        isActive
          ? "bg-emerald-100 text-emerald-800 border-emerald-200"
          : "bg-orange-100 text-orange-800 border-orange-200"
      )}
    >
      {isActive ? "Active" : "Inactive"}
    </span>
  )
}

// ---- Create User Dialog ----

interface CreateUserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

function CreateUserDialog({ open, onOpenChange, onCreated }: CreateUserDialogProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [email, setEmail] = useState("")
  const [fullName, setFullName] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState<"user" | "admin">("user")
  const [isActive, setIsActive] = useState(true)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => {
      const body: CreateAdminUserRequest = {
        email,
        password,
        is_superuser: role === "admin",
        is_active: isActive,
      }
      if (fullName.trim()) body.full_name = fullName.trim()
      return createUser(body)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
      toast({ title: "User created", description: email })
      onCreated()
      onOpenChange(false)
      setEmail("")
      setFullName("")
      setPassword("")
      setRole("user")
      setIsActive(true)
      setFieldError(null)
    },
    onError: (err: Error & { status?: number }) => {
      if (err.status === 409 || err.status === 422) {
        setFieldError(err.message)
      } else {
        toast({ title: "Error", description: err.message, variant: "destructive" })
      }
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFieldError(null)
    mutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="create-user-dialog">
        <DialogHeader>
          <DialogTitle className="font-montserrat">Create User</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              data-testid="email-input"
              type="email"
              required
              placeholder="user@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="full_name">Full name (optional)</Label>
            <Input
              id="full_name"
              data-testid="full-name-input"
              placeholder="Jane Doe"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              data-testid="password-input"
              type="password"
              required
              minLength={8}
              placeholder="Min 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="role">Role</Label>
            <Select value={role} onValueChange={(v) => setRole(v as "user" | "admin")}>
              <SelectTrigger id="role" data-testid="role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">User</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="active">Status</Label>
            <Select
              value={isActive ? "active" : "inactive"}
              onValueChange={(v) => setIsActive(v === "active")}
            >
              <SelectTrigger id="active" data-testid="active-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {fieldError && (
            <p data-testid="field-error" className="text-sm text-red-600">
              {fieldError}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              data-testid="create-user-submit"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Creating…" : "Create User"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---- Confirm Delete Dialog ----

interface ConfirmDeleteDialogProps {
  user: AdminUser | null
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDeleteDialog({ user, onConfirm, onCancel }: ConfirmDeleteDialogProps) {
  return (
    <Dialog open={user !== null} onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogContent className="sm:max-w-sm" data-testid="confirm-delete-dialog">
        <DialogHeader>
          <DialogTitle className="font-montserrat">Delete user?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-zinc-600">
          This will permanently delete <strong>{user?.email}</strong>. This cannot be undone.
        </p>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            data-testid="confirm-delete-submit"
            onClick={onConfirm}
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---- Users Table Row Actions ----

interface RowActionsProps {
  user: AdminUser
  isSelf: boolean
  onActivate: () => void
  onDeactivate: () => void
  onPromote: () => void
  onDemote: () => void
  onDelete: () => void
}

function RowActions({
  user,
  isSelf,
  onActivate,
  onDeactivate,
  onPromote,
  onDemote,
  onDelete,
}: RowActionsProps) {
  const disabled = isSelf

  return (
    <div className="flex items-center gap-1.5" data-testid={`row-actions-${user.id}`}>
      {user.is_active ? (
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          data-testid={`deactivate-${user.id}`}
          onClick={onDeactivate}
          className="h-7 text-xs"
        >
          Deactivate
        </Button>
      ) : (
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          data-testid={`activate-${user.id}`}
          onClick={onActivate}
          className="h-7 text-xs"
        >
          Activate
        </Button>
      )}

      {user.is_superuser ? (
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          data-testid={`demote-${user.id}`}
          onClick={onDemote}
          className="h-7 text-xs"
        >
          Demote
        </Button>
      ) : (
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          data-testid={`promote-${user.id}`}
          onClick={onPromote}
          className="h-7 text-xs"
        >
          Promote
        </Button>
      )}

      <Button
        size="sm"
        variant="destructive"
        disabled={disabled}
        data-testid={`delete-${user.id}`}
        onClick={onDelete}
        className="h-7 text-xs"
      >
        Delete
      </Button>
    </div>
  )
}

// ---- Main Page ----

function UsersPageInner() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // URL-driven state
  const page = Number(searchParams.get("page") ?? "1")
  const search = searchParams.get("search") ?? ""
  const role = (searchParams.get("role") ?? "") as "admin" | "user" | ""
  const activeParam = searchParams.get("active")
  const activeFilter = activeParam === "true" ? true : activeParam === "false" ? false : undefined

  // Local UI state
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null)
  const [searchInput, setSearchInput] = useState(search)

  // Current admin user (to detect own row)
  const { data: me } = useQuery<AuthUser>({
    queryKey: ["me"],
    queryFn: getMeApi,
  })

  const queryParams: AdminUsersListParams = {
    page,
    page_size: PAGE_SIZE,
    ...(search ? { search } : {}),
    ...(role ? { role } : {}),
    ...(activeFilter != null ? { active: activeFilter } : {}),
  }

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", queryParams],
    queryFn: () => listUsers(queryParams),
  })

  const users = data?.users ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    params.delete("page")
    router.push(`${pathname}?${params.toString()}`)
  }

  function updatePage(newPage: number) {
    const params = new URLSearchParams(searchParams.toString())
    params.set("page", String(newPage))
    router.push(`${pathname}?${params.toString()}`)
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault()
    updateParam("search", searchInput)
  }

  // Shared mutation for PATCH operations
  const patchMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { is_active?: boolean; is_superuser?: boolean } }) =>
      updateUser(id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
    },
    onError: (err: Error & { status?: number }) => {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] })
      setDeleteTarget(null)
      toast({ title: "User deleted" })
    },
    onError: (err: Error & { status?: number }) => {
      setDeleteTarget(null)
      toast({ title: "Error", description: err.message, variant: "destructive" })
    },
  })

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-5 border-b border-zinc-200 bg-white flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-indigo-600" />
          <h1 className="text-xl font-bold font-montserrat text-zinc-900">
            User Management
          </h1>
        </div>
        <Button
          data-testid="create-user-button"
          onClick={() => setCreateOpen(true)}
          className="gap-1.5"
        >
          <Plus className="w-4 h-4" />
          Create User
        </Button>
      </div>

      {/* Filters */}
      <div className="shrink-0 px-6 py-3 border-b border-zinc-100 bg-white flex items-center gap-3 flex-wrap">
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
          <Input
            data-testid="search-input"
            placeholder="Search by email or name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-64 h-8 text-sm"
          />
          <Button type="submit" size="sm" variant="outline" className="h-8 text-xs">
            Search
          </Button>
        </form>

        <Select value={role || "all"} onValueChange={(v) => updateParam("role", v === "all" ? "" : v)}>
          <SelectTrigger data-testid="filter-role" className="w-32 h-8 text-sm">
            <SelectValue placeholder="All roles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
            <SelectItem value="user">User</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={activeFilter == null ? "all" : activeFilter ? "active" : "inactive"}
          onValueChange={(v) =>
            updateParam("active", v === "all" ? "" : v === "active" ? "true" : "false")
          }
        >
          <SelectTrigger data-testid="filter-active" className="w-36 h-8 text-sm">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <span className="text-sm text-zinc-400">Loading…</span>
          </div>
        ) : (
          <div className="rounded-md border border-zinc-200 bg-white overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-sm text-zinc-400 py-10">
                      No users found.
                    </TableCell>
                  </TableRow>
                ) : (
                  users.map((user) => {
                    const isSelf = me?.id === user.id
                    return (
                      <TableRow key={user.id} data-testid={`user-row-${user.id}`}>
                        <TableCell className="font-mono text-sm">{user.email}</TableCell>
                        <TableCell className="text-sm text-zinc-600">
                          {user.full_name ?? <span className="text-zinc-300">—</span>}
                        </TableCell>
                        <TableCell>
                          <RoleBadge isSuperuser={user.is_superuser} />
                        </TableCell>
                        <TableCell>
                          <ActiveChip isActive={user.is_active} />
                        </TableCell>
                        <TableCell className="text-xs text-zinc-500">
                          {new Date(user.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <RowActions
                            user={user}
                            isSelf={isSelf}
                            onActivate={() =>
                              patchMutation.mutate({ id: user.id, patch: { is_active: true } })
                            }
                            onDeactivate={() =>
                              patchMutation.mutate({ id: user.id, patch: { is_active: false } })
                            }
                            onPromote={() =>
                              patchMutation.mutate({ id: user.id, patch: { is_superuser: true } })
                            }
                            onDemote={() =>
                              patchMutation.mutate({ id: user.id, patch: { is_superuser: false } })
                            }
                            onDelete={() => setDeleteTarget(user)}
                          />
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Pagination */}
        <div className="mt-4 flex items-center justify-between text-sm text-zinc-500">
          <span>
            {total > 0 ? `${total} user${total !== 1 ? "s" : ""} total` : ""}
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              data-testid="page-prev"
              disabled={page <= 1}
              onClick={() => updatePage(page - 1)}
              className="h-7 text-xs"
            >
              Previous
            </Button>
            <span className="text-xs">
              Page {page} of {totalPages}
            </span>
            <Button
              size="sm"
              variant="outline"
              data-testid="page-next"
              disabled={page >= totalPages}
              onClick={() => updatePage(page + 1)}
              className="h-7 text-xs"
            >
              Next
            </Button>
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <CreateUserDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {}}
      />

      <ConfirmDeleteDialog
        user={deleteTarget}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}

export default function UsersPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-zinc-400">Loading…</div>}>
      <UsersPageInner />
    </Suspense>
  )
}
