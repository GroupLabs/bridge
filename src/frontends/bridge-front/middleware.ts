import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isPublicRoute = createRouteMatcher(['/sign-in(.*)', '/sign-up(.*)'])

export default clerkMiddleware((auth, request) => {
  // Check if it's a POST request to /, /connectors, /databases, or /files
  if (
    (request.method === 'POST' && request.url.includes('/')) ||
    request.url.includes('/connectors') ||
    request.url.includes('/databases') ||
    request.url.includes('/files')
  ) {
    // Do not apply Clerk middleware for POST requests to /connectors, /databases, or /files
    return
  }

  if (!isPublicRoute(request)) {
    auth().protect()
  }
})

export const config = {
  matcher: [
    '/((?!_next/image|_next/static|favicon.ico).*)',
    '/',
    '/connectors',
    '/databases',
    '/files'
  ]
}
