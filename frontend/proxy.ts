import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js proxy for route protection.
 * 
 * Performs optimistic cookie check to protect routes like /dashboard
 * and redirects unauthenticated users to sign-in page.
 * 
 * This is a lightweight check - no database queries or heavy logic.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // IMPORTANT: Skip proxy logic for UploadThing API routes
  // UploadThing needs to handle its own authentication via middleware
  if (pathname.startsWith("/api/uploadthing")) {
    return NextResponse.next();
  }

  // Read Better Auth session cookie
  const sessionCookie = request.cookies.get("better-auth.session-token");

  // Redirect authenticated users away from /signup to /redirect
  if (pathname.startsWith("/signup") && sessionCookie) {
    const url = request.nextUrl.clone();
    url.pathname = "/redirect";
    url.searchParams.delete("callbackUrl");
    return NextResponse.redirect(url);
  }

  // Redirect authenticated users away from /sign-in to /redirect
  if (pathname.startsWith("/sign-in") && sessionCookie) {
    const url = request.nextUrl.clone();
    url.pathname = "/redirect";
    // Clear callbackUrl to avoid loops
    url.searchParams.delete("callbackUrl");
    return NextResponse.redirect(url);
  }

  // Protect /dashboard routes - redirect to sign-in if no session cookie
  if (pathname.startsWith("/dashboard") && !sessionCookie) {
    const url = request.nextUrl.clone();
    url.pathname = "/signup";
    url.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(url);
  }

  // Optionally protect /onboarding if that flow requires authentication
  // Uncomment if onboarding should be protected:
  // if (pathname.startsWith("/onboarding") && !sessionCookie) {
  //   const url = request.nextUrl.clone();
  //   url.pathname = "/sign-in";
  //   url.searchParams.set("callbackUrl", pathname);
  //   return NextResponse.redirect(url);
  // }

  // Allow all other requests to proceed
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
