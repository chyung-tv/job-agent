# Job Agent Frontend — Step-by-Step Implementation Guide

This guide breaks down the [frontend implementation guideline](frontend-implementation-guideline.md) into ordered steps. Each step states **backend work first** (if any), the **stack** in use, **how to implement** it, and **dependencies to install**.

**Constraints (apply to all steps):** Prisma is **read-only** (no `prisma migrate` / `prisma db push`). Use `job_agent_ui` for `DATABASE_URL`. `NEXT_PUBLIC_API_URL` must include the `/api/v1` prefix when using Caddy. **API_KEY** is used only in Server Actions (never sent to the client).

Pro-Tip 1: The "Zustand Hydration" Fix When using persist in Zustand with Next.js, you might hit "Hydration Mismatch" errors because the server doesn't have access to sessionStorage. Instruction: Tell Cursor to use a useEffect or a useHasHydrated hook before rendering components that rely on the onboarding store.

Pro-Tip 2: Shadcn "Stepper" Logic Since Shadcn doesn't have a native Stepper, tell Cursor to: "Use the Vertical Steps pattern from Radix UI or a simple mapping of an array of objects { id, label, nodeName } where the current step is derived from runStatus.node."

---

## Step 1: Types and shared interfaces (Frontend)

**Stack:** TypeScript, Prisma (generated types), **Zod** (runtime validation and type inference).

**What we’re doing:** Define workflow API request/response shapes and ensure DB types are available so services and UI stay type-safe.

**Implementation:**

1. **`frontend/types/workflow.ts`** (Manual Zod schemas for API types):
   - Create Zod schemas for workflow API contracts:
     - **Profiling:** request schema `profilingWorkflowRequestSchema` with `name`, `email`, `location`, optional `basic_info`, `cv_urls` (string array). Response schema `profilingWorkflowResponseSchema` with `run_id`, `task_id`, `status`, `status_url`, `estimated_completion_time`.
     - **Job search (from-profile):** request schema `jobSearchFromProfileRequestSchema` with `user_id`, optional `num_results`, `max_screening`. Response schema `jobSearchFromProfileResponseSchema` with `message`, `user_id`, `location`, `job_titles_count`, `job_titles`.
     - **Status (SSE):** event schema `runStatusEventSchema` with `status` (enum), optional `node`, `message`, `completed_at` (ISO string), `error_message`. Note: Backend doesn't use `step` field, only `node`.
     - **Status (GET fallback):** response schema `runStatusResponseSchema` matching `runs` table structure.
   - Export TypeScript types using `z.infer<typeof Schema>` for each schema (e.g., `export type ProfilingWorkflowRequest = z.infer<typeof profilingWorkflowRequestSchema>`)
   - Use `z.enum()` or `z.union([z.literal("pending"), ...])` for status values: `"pending"`, `"processing"`, `"completed"`, `"failed"`

2. **Prisma Models (Auto-generated TypeScript types):**
   - Prisma automatically generates TypeScript types from `schema.prisma` when you run `npx prisma generate`
   - Import types directly from `@prisma/client`: `import type { User, Run, matched_jobs, artifacts, job_postings } from '@prisma/client'`
   - These types are available immediately after running `npx prisma generate` (no additional setup needed)
   - Use these types for database operations and type-safe Prisma queries

**Dependencies to install:** None. Zod is already installed (`zod@^4.3.6`). Prisma types are generated automatically by running `npx prisma generate` (already part of the workflow).

---

## Step 2: Real-time status via SSE (Backend first, then Frontend)

### 2a. Backend adaptation (FastAPI + Redis + Celery)

**Stack:** FastAPI, Redis (pub/sub), Celery, Python `redis` (async or sync).

**What we’re doing:** Add an SSE endpoint that subscribes to Redis channel `run:status:{run_id}` and stream events. Workers publish status/node updates to that channel.

**Implementation:**

1. **Dependency:** `pyproject.toml` already has `redis[hiredis]>=5.0.0`. Ensure Redis is running (same instance as Celery broker).
2. **FastAPI – SSE endpoint:**
   - Add `GET /workflow/status/{run_id}/stream` (or under `/api/v1/...` if you use that prefix). Return a **StreamingResponse** with `Content-Type: text/event-stream`.
   - In the generator: subscribe to Redis channel **`run:status:{run_id}`** (use `redis.asyncio` or run sync client in a thread). For each message, yield a line in SSE format: **`data: {json}\n\n`** (double newline after each event). Include `status`, `node` or `step`, and optional `message`, `completed_at`, `error_message` so the frontend can drive a Progress Stepper.
   - **SSE heartbeat:** If no real event is sent for a period, the connection can be dropped by the browser or proxy. The generator must send a **heartbeat** every **15 seconds** when idle: yield **`: keep-alive\n\n`** (SSE comment line) so the connection stays open.
   - Handle client disconnect (e.g. close Redis subscription and generator).
3. **Caddy – long read timeout:** In the Caddyfile, for the API `reverse_proxy` block, set a long **read timeout** (e.g. **`header_timeout 10m`** or equivalent) so long-lived SSE connections are not closed by the proxy.
4. **Celery / workflow – publish to Redis:**
   - In **BaseWorkflow** or **BaseNode**, whenever **context.status** or the **current node** changes, **publish** a JSON payload to Redis on channel **`run:status:{run_id}`**. Use the same Redis URL as the broker. Payload shape should match the `Status (SSE)` type in Step 1 (e.g. `{ "status": "processing", "node": "cv_processing", "message": "Parsing CV..." }`).
4. **Optional – Caddy:** If SSE feels delayed, add `proxy_buffering off` (or Caddy’s equivalent, e.g. `flush_interval -1`) for the API block in the Caddyfile.

**Dependencies to install:** None (Redis and FastAPI already present). Use `redis.asyncio` for the subscriber if you prefer async.

---

### 2b. Frontend – status service and useRunStatus hook

**Stack:** Next.js, native **EventSource**, TypeScript.

**What we’re doing:** Expose the SSE URL and optional GET fallback, and a hook that opens an EventSource, parses `data:` events as JSON, and exposes state for the Progress Stepper.

**Implementation:**

1. **`frontend/services/status.service.ts`**
   - `getRunStatusStreamUrl(runId: string): string` — return `${NEXT_PUBLIC_API_URL}/workflow/status/${runId}/stream` (or the path you chose in 2a). If the backend is behind Caddy on the same origin, this can be a relative path that Caddy forwards to the API.
   - Optional: `fetchRunStatus(runId: string)` — call `GET .../workflow/status/{run_id}` for one-off or fallback when SSE is unavailable.
2. **`frontend/hooks/useRunStatus.ts`**
   - Accept `runId: string` (and optionally an `enabled` flag). Build SSE URL with `status.service`.
   - Use **`new EventSource(sseUrl)`**. On `message`, parse `event.data` as JSON and update state (e.g. `status`, `node`, `message`, `completed_at`).
   - Close the EventSource when `status` is `completed` or `failed`, or on component unmount (e.g. in a `useEffect` cleanup).
   - Return `{ status, node, message, completed_at, error_message, isConnected }` (or similar) for the UI.

**Dependencies to install:** None (EventSource is built into the browser).

---

## Step 3: Workflow triggers via Server Actions (Frontend)

**Stack:** Next.js 16+ **Server Actions**, `fetch`, TypeScript.

**What we’re doing:** Call the FastAPI workflow endpoints from **Server Actions** only so **API_KEY** stays server-side and the browser never sees it.

**Implementation:**

1. **`frontend/actions/workflow.ts`** — Export **Server Actions** (e.g. `triggerProfiling`, `triggerJobSearch`, `triggerJobSearchFromProfile`) that run on the server. Each action calls `POST ${API_URL}/workflow/profiling` (or `/workflow/job-search`, `/workflow/job-search/from-profile`) with `X-API-Key` or `Authorization: Bearer` using **`process.env.API_KEY`**. Return typed response (run_id, status_url, etc.) or throw with a user-friendly message on non-2xx. Use types from `frontend/types/workflow.ts`.
2. **`frontend/services/workflow.service.ts`** (optional): Keep as a helper for URLs or params if needed; the actual `fetch` with API_KEY must happen only in Server Actions in `actions/workflow.ts`.

**Dependencies to install:** None.

---

## Step 4: Optional GET status fallback (Backend)

**Stack:** FastAPI, SQLAlchemy, existing `Run` model.

**What we’re doing:** Allow one-off status checks (e.g. for clients that don’t support SSE or for debugging).

**Implementation:**

1. Add **`GET /workflow/status/{run_id}`** (or under `/api/v1/...`). Verify API key (same as other workflow routes).
2. Load `Run` by `run_id` from the DB. Return JSON with `status`, `task_id`, `completed_at`, `error_message`, and any other Run fields the frontend needs. Return 404 if run not found.

**Dependencies to install:** None.

---

## Step 5: Route protection with proxy.ts (Frontend)

**Stack:** Next.js 16+ (**proxy.ts** as network boundary).

**What we’re doing:** Replace middleware with proxy; protect `/dashboard` (and optionally `/onboarding`) with an optimistic cookie check and redirect to sign-in when missing.

**Implementation:**

1. If the project still has **`middleware.ts`**, run **`npx @next/codemod@canary middleware-to-proxy`** or manually rename it to **`frontend/proxy.ts`** and change the exported function to **`export function proxy(request: NextRequest)`**.
2. In **`frontend/proxy.ts`**:
   - Read **`request.cookies.get("better-auth.session-token")`**. If pathname starts with `/dashboard` and the cookie is missing, redirect to **`/sign-in`** with **`callbackUrl=<pathname>`** in the query.
   - Optionally do the same for `/onboarding` if that flow is for signed-in users only.
   - **`return NextResponse.next()`** otherwise. Do not run DB or heavy logic here.
3. Set **`config.matcher`** so proxy does not run on `api`, `_next/static`, `_next/image`, `favicon.ico` (e.g. `matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)']`).

**Dependencies to install:** None.

---

## Step 6: Better Auth config and sign-in page (Frontend)

**Stack:** Next.js App Router, **Better Auth** (existing).

**What we’re doing:** Set **trustHost** so Better Auth works behind Caddy, then provide a sign-in page so redirects from proxy have a target.

**Implementation:**

1. **`frontend/lib/auth.ts`** — Set **`advanced: { trustHost: true }`** in the Better Auth config. Without this, redirects after Google login may point to `http://localhost:3000` instead of your public VPS domain when running behind Caddy.
2. Add **`frontend/app/(auth)/sign-in/page.tsx`** (or under the auth group you use). Read **`callbackUrl`** from searchParams and pass it to Better Auth’s sign-in (e.g. redirect after success to `callbackUrl` or default `/dashboard`).
3. Use **`authClient.signIn.social({ provider: "google", callbackURL: callbackUrl })`** (or the equivalent in your Better Auth version) and a simple UI (e.g. “Sign in with Google”). Ensure **`/api/auth/*`** is handled by the existing Better Auth route and is not blocked by proxy.

**Dependencies to install:** None (Better Auth already installed).

---

## Step 7: Onboarding store (Zustand + persist) and identity step (Frontend)

**Stack:** Next.js App Router, **Zustand** (with **persist** middleware using **sessionStorage**), **Better Auth** (session), **Prisma** (optional write for `user.location`).

**What we’re doing:** Create an onboarding store that survives page refresh (so the Vibe Check Cultural Persona summary is not lost), then implement the identity step that reads/writes this store.

**Implementation:**

1. **`frontend/store/useOnboardingStore.ts`** — Create a Zustand store for onboarding state: `name`, `email`, `location`, **`basic_info`** (Cultural Persona from Vibe Check), **`cv_urls`** (array of public URLs). Expose an action **`addCvUrl(url: string)`** (or equivalent) so UploadThing’s **onClientUploadComplete** can append each uploaded file’s URL. Use the **`persist`** middleware with **`storage: sessionStorage`** so that if the user refreshes during step 2 (Vibe Check), the summary (and cv_urls) is not wiped.
2. Add **`frontend/app/onboarding/page.tsx`**. Fetch session; pre-fill **name** and **email** from session (or from store); show an input for **location** (required for profiling). On "Continue", write name, email, location to **useOnboardingStore** and navigate to the next step (CV upload or Vibe Check).
3. Optional: If the backend allows the UI user to update `user.location`, add a Server Action in **`frontend/actions/user.ts`** that uses Prisma to update **`user.location`** by `user.id` from the session. Otherwise only keep location in the store.

**Dependencies to install:** **`zustand`** (persist middleware is usually included).

---

## Step 7b: PDF upload (UploadThing) (Frontend)

**Stack:** Next.js App Router, [UploadThing](http://docs.uploadthing.com/getting-started/appdir) (`uploadthing`, `@uploadthing/react`).

**What we're doing:** Capture PDF file uploads via UploadThing and store the returned public URLs in **useOnboardingStore.cv_urls** so the profiling backend receives a list of CV URLs.

**Implementation:**

1. **Config — FileRouter and API route:**
   - **`frontend/app/api/uploadthing/core.ts`**: Create a **FileRouter** with a single route **`pdfUploader`**. Use `createUploadthing()` from `uploadthing/next`. Configure the route to accept **pdf** type with **maxFileSize: "4MB"** (and optional `maxFileCount`). Optionally add **middleware** (e.g. auth) and **onUploadComplete** (e.g. log). Export the router type (e.g. `export type OurFileRouter = typeof ourFileRouter`) for the client.
   - **`frontend/app/api/uploadthing/route.ts`**: Use **`createRouteHandler`** from `uploadthing/next` with the router from `core.ts`. Export **GET** and **POST**.
   - Add **`UPLOADTHING_TOKEN`** to `.env` (from [UploadThing dashboard](https://uploadthing.com)).
2. **Component:** In **`frontend/app/onboarding/page.tsx`** (on the step where the user adds their CV), mount the **UploadDropzone** from `@uploadthing/react`. Re-export it with your router type (e.g. from `lib/uploadthing.ts` as in [UploadThing App Router docs](http://docs.uploadthing.com/getting-started/appdir)) so types match. Use **`endpoint="pdfUploader"`**.
3. **State:** In **`onClientUploadComplete`**, receive the uploaded files. For each file, take **`file.url`** (the public link) and call **`useOnboardingStore.getState().addCvUrl(file.url)`** (or your store’s equivalent) so the URL is pushed into the **cv_urls** array in the store.
4. **Final action:** When the user submits the profiling workflow (Step 9), pass **`cv_urls`** from **useOnboardingStore** in the payload to the Server Action **triggerProfiling**. The FastAPI backend expects **cv_urls** as a list of public URLs; ensure the store’s **cv_urls** are included in that payload.

**Dependencies to install:** **`uploadthing`** and **`@uploadthing/react`**. Optional: add **UploadThing Tailwind** (`withUt`) if you use their theming (see [UploadThing docs](http://docs.uploadthing.com/getting-started/appdir)).

---

## Step 8: Vibe Check chat (Frontend)

**Stack:** Next.js, **Vercel AI SDK** (`useChat` or equivalent), React.

**What we’re doing:** A short chat that collects work culture preferences and produces a 2–3 paragraph “Cultural Persona” summary to send as `basic_info` in the profiling request.

**Implementation:**

1. Add a chat UI (e.g. in **`frontend/components/chat/VibeCheckChat.tsx`**). Use **Vercel AI SDK**’s **`useChat`** (or similar) with your AI provider endpoint (e.g. Next.js API route that streams from OpenAI/Anthropic). System prompt should ask about work culture, team size, remote/hybrid; instruct the model to end with a 2–3 paragraph “Cultural Persona” summary.
2. When the user finishes (e.g. “Done” or after a fixed number of turns), take the last assistant message or a dedicated summary field and store it as **basic_info** in **useOnboardingStore** (from Step 7). Because the store uses **persist (sessionStorage)**, a refresh during the chat does not lose the Cultural Persona summary.
3. Reuse or add **`frontend/hooks/useVibeChat.ts`** if you need a thin wrapper around `useChat` (e.g. to enforce summary format or to expose `basic_info`).

**Dependencies to install:**

- **`ai`** (Vercel AI SDK) and **`@ai-sdk/react`** (or the package that provides `useChat` in your SDK version). If you use a specific model, add the provider package (e.g. `@ai-sdk/openai`).

---

## Step 9: Onboarding – submit profiling and processing page (Frontend)

**Stack:** Next.js, **Server Actions** (`actions/workflow.ts`), **useRunStatus**, Shadcn UI (for Progress Stepper or list).

**What we’re doing:** Call the profiling workflow, redirect to a processing page, stream status via SSE, show a Progress Stepper, and redirect to the dashboard when done.

**Implementation:**

1. On the last onboarding step, collect **name, email, location, basic_info** (from **useOnboardingStore** — Vibe Check step), and **cv_urls** from **useOnboardingStore** (populated by UploadThing in Step 7b via **onClientUploadComplete**). Call the **Server Action** **`triggerProfiling`** from **`actions/workflow.ts`** with these params, **ensuring cv_urls from the store are included in the payload** to the FastAPI backend (do not call a client-side service with API_KEY). On success, redirect to **`/onboarding/processing?run_id=<run_id>`**.
2. **`frontend/app/onboarding/processing/page.tsx`**: Read **`run_id`** from searchParams. Use **`useRunStatus(runId)`** to open the SSE stream and get `status`, `node`, `message`. Render a **Progress Stepper** (e.g. steps: “Submitted” → “Parsing CV” → “Building profile” → “Complete”) and set the active step from `node` or `status`. On `status === "completed"`, redirect to **`/dashboard/overview`** (or profile). On `status === "failed"`, show `error_message` and a link back to onboarding or dashboard.
3. Add a Shadcn **Stepper** or a simple ordered list with “current” and “done” styles if you don’t have a Stepper component yet.

**Dependencies to install:** None beyond existing Shadcn. Add a Stepper from Shadcn or build a minimal one (e.g. list + current index from `node`).

---

## Step 10: Dashboard layout and overview (Frontend)

**Stack:** Next.js App Router, **Prisma** (read-only), **useRunStatus**, Shadcn layout components.

**What we’re doing:** A protected dashboard with a sidebar and an overview page that lists runs and shows live status for in-progress ones.

**Implementation:**

1. **`frontend/app/(dashboard)/layout.tsx`**: Add a persistent **Sidebar** (e.g. links to `/dashboard/overview`, `/dashboard/profile`, `/dashboard/matches`). Provide user context (e.g. session or user id) for child pages. Use Server Component to fetch user if needed, or pass session from a parent.
2. **`frontend/app/(dashboard)/overview/page.tsx`**: With Prisma, run **`prisma.run.findMany({ where: { user_id: session.user.id }, orderBy: { created_at: 'desc' }, take: 20 })`** (or equivalent). Render a list of runs (id, status, created_at). For each run with `status` not in `['completed', 'failed']`, use **`useRunStatus(run.id)`** and show a small **Progress Stepper** or status line (e.g. “Processing – CV parsing”). When SSE reports `completed` or `failed`, refresh or update the list (e.g. via state so the row updates).

**Dependencies to install:** None (Prisma and Shadcn already in project). Add Shadcn **Sidebar** or **Navigation** if not present.

---

## Step 11: Profile page – Master Identity (Frontend)

**Stack:** Next.js App Router, **Prisma** (read-only), Shadcn UI.

**What we’re doing:** Show the user’s “Master Identity”: name, email, location, profile_text (from CV + backend), and optionally the stored vibe summary.

**Implementation:**

1. **`frontend/app/(dashboard)/profile/page.tsx`**: In a Server Component (or Server Action), load **user** by id from the session: **`prisma.user.findUnique({ where: { id: session.user.id } })`**. Select `name`, `email`, `image`, `location`, **`profile_text`**. Render a simple profile card or form (read-only or editable depending on product). If “vibe” is stored in `profile_text` or a dedicated field, show it as a short summary section.

**Dependencies to install:** None.

---

## Step 12: Match catalog – list and detail (Frontend)

**Stack:** Next.js App Router, **Prisma** (read-only), Shadcn UI.

**What we’re doing:** List the user’s matched jobs with reason and link to a detail page; detail page shows Tailored CV (PDF), Cover Letter, and application link.

**Implementation:**

1. **`frontend/app/(dashboard)/matches/page.tsx`**: Query **`prisma.matched_jobs.findMany({ where: { user_id: session.user.id }, include: { job_postings: true, artifacts: true }, orderBy: { created_at: 'desc' } })`**. Render a grid or list of **MatchCard** components: job title (`job_postings.title`), company (`job_postings.company_name`), **reason** (`matched_jobs.reason`), and `is_match`. Link each card to **`/dashboard/matches/[id]`** with `matched_jobs.id`.
2. **`frontend/app/(dashboard)/matches/[id]/page.tsx`**: Load **matched_job** by id and `user_id`, with **`include: { job_postings: true, artifacts: true }`**. Show job title, company, reason. For **Tailored CV**: use **`artifacts.cv?.pdf_url`** (backend stores `{ "pdf_url": "https://..." }`). For **Cover Letter**: render **`artifacts.cover_letter`** (JSON or text). Add an “Apply” button: **`application_link?.link`** (with fallback if structure differs). Implement **`frontend/components/matches/MatchCard.tsx`**, **PDFViewer** (or iframe), and **ActionPanel** (Apply button) as needed.
3. **PDF security and Download/Print:** Use **`sandbox="allow-scripts allow-same-origin"`** on the PDF preview **`<iframe>`** for security. Implement a "Download" (or "Print") button using a hidden **`<a href={pdf_url} download>`** (or `window.open` for print) so the user can save or print the tailored CV (some browsers block iframe downloads). **Security check (handoff):** Confirm whether `pdf_url` in the DB are **signed S3 URLs** (time-limited) or **public URLs**; if signed, do not cache beyond validity.

**Dependencies to install:** For **PDF viewing** in the browser, choose one:
- **`react-pdf`** (or **`@react-pdf-viewer/core`**) to render the PDF from `pdf_url`, or
- A simple **`<iframe src={artifact.cv?.pdf_url} sandbox="allow-scripts allow-same-origin" />`** if the URL is CORS-friendly and you don’t need custom controls.

---

## Step 13: Polish – error, loading, and empty states (Frontend)

**Stack:** Next.js, Shadcn UI, existing components.

**What we’re doing:** Consistent error, loading, and empty states for onboarding, dashboard overview, profile, and matches.

**Implementation:**

1. **Onboarding:** Loading while session is loading; error if profiling trigger fails (show message and retry or “Back”); empty state if no CV URLs yet (prompt user to add links or upload).
2. **Overview:** Loading skeleton while runs are fetched; empty state “No runs yet” with link to onboarding or job search; error state if Prisma or session fails.
3. **Profile:** Loading and error (e.g. user not found).
4. **Matches:** Loading skeleton; empty “No matches yet”; error on failed fetch. Detail: 404 if match not found or not owned by user.

**Dependencies to install:** None (use Shadcn **Skeleton**, **Alert**, and existing patterns).

---

## Quick reference: stacks and dependencies by step

| Step | Stack | New dependencies |
|------|--------|-------------------|
| 1 | TypeScript, Prisma | — |
| 2a | FastAPI, Redis, Celery | — (redis in pyproject) |
| 2b | Next.js, EventSource | — |
| 3 | Next.js 16+ Server Actions | — |
| 4 | FastAPI, SQLAlchemy | — |
| 5 | Next.js 16+ proxy | — |
| 6 | Next.js, Better Auth (trustHost) | — |
| 7 | Next.js, Zustand (persist), Better Auth, Prisma | `zustand` |
| 7b | Next.js, UploadThing | `uploadthing`, `@uploadthing/react` |
| 8 | Next.js, Vercel AI SDK | `ai`, `@ai-sdk/react` (+ provider if needed) |
| 9 | Next.js, Server Actions, useRunStatus, Shadcn | Stepper or minimal custom |
| 10 | Next.js, Prisma, useRunStatus, Shadcn | Sidebar/nav if missing |
| 11 | Next.js, Prisma, Shadcn | — |
| 12 | Next.js, Prisma, Shadcn | `react-pdf` or iframe only |
| 13 | Next.js, Shadcn | — |

---

## Environment variables (reminder)

- **BETTER_AUTH_URL** / **NEXT_PUBLIC_BETTER_AUTH_URL**: Public app URL (e.g. `https://app.example.com`).
- **DATABASE_URL**: Postgres with **job_agent_ui** (read-only); never use backend admin user.
- **NEXT_PUBLIC_API_URL**: Must include **`/api/v1`** when Caddy routes `/api/v1/*` to FastAPI.
- **API_KEY**: Used for FastAPI workflow and status endpoints (**server-side only** — never send to the client; use Server Actions).
- **UPLOADTHING_TOKEN**: UploadThing SDK token for PDF upload (get from [UploadThing dashboard](https://uploadthing.com)); required for onboarding CV upload.

## Summary Checklist for Cursor

- [ ] **`proxy.ts`** is implemented with optimistic cookie check; protected routes redirect to sign-in when unauthenticated.
- [ ] **SSE** Progress Stepper is active on **`/dashboard/overview`** and **`/onboarding/processing`**; backend sends heartbeat every 15s; Caddy has long read timeout for API.
- [ ] **Prisma 7** is used in Server Components for the Match Catalog (and profile/overview reads); no migrate/db push.
- [ ] **Vercel AI SDK** generates the **`basic_info`** (Cultural Persona) summary; it is stored in Zustand with sessionStorage persist so refresh does not lose it.
- [ ] **Workflow triggers** (profiling, job-search, from-profile) are invoked via **Server Actions** only; API_KEY is never sent to the client.
- [ ] **Better Auth** has `advanced.trustHost = true` in `lib/auth.ts`.
- [ ] **PDF upload (UploadThing):** `app/api/uploadthing/route.ts` + `core.ts` with **pdfUploader** (4MB, pdf); **UploadDropzone** in `app/onboarding/page.tsx`; **onClientUploadComplete** appends **file.url** to **cv_urls** in **useOnboardingStore**; final submission (triggerProfiling) includes **cv_urls** from store in the payload to FastAPI.
