import { NextRequest, NextResponse } from "next/server"

const AUTH_COOKIE = "forma_access_token"
const AUTH_ROUTES = ["/login", "/signup", "/verify-email", "/forgot-password", "/reset-password", "/activate"]

function isAuthRoute(pathname: string): boolean {
  return AUTH_ROUTES.some((route) => pathname.startsWith(route))
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.includes(".") ||
    pathname.startsWith("/api/")
  ) {
    return NextResponse.next()
  }

  const token = request.cookies.get(AUTH_COOKIE)?.value
  const isAuthenticated = !!token

  if (isAuthenticated) {
    if (isAuthRoute(pathname)) {
      const loginUrl = new URL("/dashboard", request.url)
      return NextResponse.redirect(loginUrl)
    }
    return NextResponse.next()
  } else {
    if (!isAuthRoute(pathname)) {
      const loginUrl = new URL("/login", request.url)
      loginUrl.searchParams.set("redirect", pathname)
      return NextResponse.redirect(loginUrl)
    }
    return NextResponse.next()
  }
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/).*)",
  ],
}
