import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js 16 proxy for routing.
 * 
 * Per Next.js 16 best practices, proxy.ts is for ROUTING ONLY:
 * - Rewrites, redirects, headers
 * - NOT for authentication (that belongs in layout.tsx Server Layout Guards)
 * 
 * Auth is handled by:
 * - dashboard/layout.tsx - checks session and redirects to /signup if invalid
 * - signup/page.tsx - client-side check redirects authenticated users
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip proxy logic for UploadThing API routes
  if (pathname.startsWith("/api/uploadthing")) {
    return NextResponse.next();
  }

  // All auth logic is handled by layout.tsx (Server Layout Guards)
  // This prevents redirect loops caused by cookie/session mismatch
  return NextResponse.next();
}

/**
 * Proxy configuration - excludes API routes, static files, and Next.js internals.
 * 
 * IMPORTANT: Excludes /api/uploadthing to allow UploadThing requests to pass through
 * without being intercepted by authentication checks.
 */
export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|_next).*)"],
};
