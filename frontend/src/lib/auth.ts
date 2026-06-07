/**
 * Auth client: token storage, API calls, and session management.
 */

const USER_KEY = "forma_user"

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_superuser?: boolean
  avatar_url?: string | null
}

export interface AuthState {
  token: string | null
  user: AuthUser | null
}

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------

const TOKEN_KEY = "forma_access_token"
const AUTH_COOKIE = "forma_access_token"
export const COOKIE_MAX_AGE = 60 * 60 * 8 // 8 hours

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return
  sessionStorage.setItem(TOKEN_KEY, token)
  setAuthCookie(token)
}

export function clearToken(): void {
  if (typeof window === "undefined") return
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
}

export function setAuthCookie(token: string): void {
  if (typeof window === "undefined") return
  const secure = window.location.protocol === "https:" ? "; Secure" : ""
  document.cookie = `${AUTH_COOKIE}=${token}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax${secure}`
}

export function clearAuthCookie(): void {
  if (typeof window === "undefined") return
  document.cookie = `${AUTH_COOKIE}=; path=/; max-age=0`
}

// ---------------------------------------------------------------------------
// User storage
// ---------------------------------------------------------------------------

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null
  const raw = sessionStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export function setStoredUser(user: AuthUser): void {
  if (typeof window === "undefined") return
  sessionStorage.setItem(USER_KEY, JSON.stringify(user))
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

export async function authFetch(
  path: string,
  init?: RequestInit & { throwOnError?: boolean }
): Promise<Response> {
  const isFormData = init?.body instanceof FormData

  async function doFetch(token: string | null): Promise<Response> {
    const headers: Record<string, string> = {
      ...((init?.headers as Record<string, string>) || {}),
    }
    if (token) {
      headers["Authorization"] = `Bearer ${token}`
    }
    if (isFormData) {
      delete headers["Content-Type"]
    }
    const res = await fetch(`/api${path}`, { ...init, headers })

    // Auto-refresh on 401 if we have a refresh cookie and haven't retried yet
    if (
      res.status === 401 &&
      token !== null &&
      document.cookie.includes("refresh_token=")
    ) {
      const newToken = await refreshAccessToken()
      if (newToken) {
        return doFetch(newToken)
      }
    }

    return res
  }

  const token = getToken()
  const res = await doFetch(token)
  if (init?.throwOnError !== false && !res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res
}

// ---------------------------------------------------------------------------
// Auth API calls
// ---------------------------------------------------------------------------

export async function registerApi(data: {
  email: string
  password: string
  full_name?: string
}): Promise<void> {
  const res = await authFetch("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    throwOnError: true,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }))
    throw new Error(err.detail || "Registration failed")
  }
}

// ---------------------------------------------------------------------------
// Login — returns access_token from JSON body.
// ---------------------------------------------------------------------------
export async function loginApi(data: {
  email: string
  password: string
}): Promise<{ access_token: string }> {
  const res = await authFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    throwOnError: false,
  })
  if (res.status === 429) {
    const err = await res.json().catch(() => ({ detail: "Too many attempts. Please try again later." }))
    throw new Error(err.detail || "Too many attempts. Please try again later.")
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Invalid credentials" }))
    throw new Error(err.detail || "Invalid credentials")
  }
  const data2 = await res.json()
  return data2 as { access_token: string }
}

export async function logoutApi(): Promise<void> {
  await authFetch("/auth/logout", {
    method: "POST",
    throwOnError: false,
  })
  clearToken()
  clearAuthCookie()
}

export async function getMeApi(): Promise<AuthUser> {
  const res = await authFetch("/auth/me", { throwOnError: false })
  if (!res.ok) {
    clearToken()
    throw new Error("Not authenticated")
  }
  const user = await res.json()
  return user as AuthUser
}

export async function refreshAccessToken(): Promise<string | null> {
  try {
    const csrfCookie = (() => {
      const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
      return match ? decodeURIComponent(match[1]) : ""
    })()

    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfCookie,
      },
      credentials: "include",
    })

    if (!res.ok) {
      clearToken()
      return null
    }

    const data = await res.json()
    if (data.access_token) {
      setToken(data.access_token)
      return data.access_token
    }
    return null
  } catch {
    return null
  }
}

export async function forgotPasswordApi(email: string): Promise<{ message: string }> {
  const res = await authFetch("/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
    throwOnError: false,
  })
  const data = await res.json()
  return data as { message: string }
}

export async function checkEmailExists(email: string): Promise<void> {
  const res = await authFetch("/auth/forgot-password?check_only=true", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
    throwOnError: false,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail ?? "Email not found")
  }
}

export async function resetPasswordApi(
  token: string,
  new_password: string
): Promise<{ message: string }> {
  const res = await authFetch("/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password }),
    throwOnError: false,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Reset failed" }))
    throw new Error(err.detail || "Reset failed")
  }
  return await res.json()
}

// ---------------------------------------------------------------------------
// Session bootstrap
// ---------------------------------------------------------------------------

export async function bootstrapSession(): Promise<AuthUser | null> {
  try {
    const user = await getMeApi()
    setStoredUser(user)
    return user
  } catch {
    clearToken()
    return null
  }
}
