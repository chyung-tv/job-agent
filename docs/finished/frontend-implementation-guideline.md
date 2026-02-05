# Job Agent Frontend — First Draft Implementation Guideline

This document is a **first-draft implementation guideline** for the Job Agent Next.js frontend. It aligns the [functional requirements](#1-functional-requirements), [draft file structure](#2-draft-file-structure), and [critical constraints](#3-critical-implementation-reminders) with the existing codebase (FastAPI, Prisma schema, Better Auth).

---

## 1. Functional Requirements (Summary)

| Area | Goal |
|------|------|
| **A. Smart Onboarding & Vibe Check** | Identity refinement (name, email, location from/after Google OAuth) → AI pre-interview chat (Vercel AI SDK) → Cultural Persona summary → `POST /workflow/profiling` with summary in `basic_info`. |
| **B. Match Catalog** | Read `matched_jobs`, `job_postings`, `artifacts` via Prisma; show match list with **Match Score** (or `is_match`/reason), **AI Reasoning** (`reason`), Tailored CV (PDF URL) and Cover Letter preview, plus `application_link`. |
| **C. Real-time Dashboard & History** | Use `runs` table + **SSE (Server-Sent Events)** via Redis for real-time status; **Progress Stepper** in Dashboard; Master Profile view from user's CV + AI Vibe summary. |

---

## 2. Draft File Structure (Mapping to Features)

```
frontend/
├── app/
│   ├── (auth)/                    # Login / Signup (existing: signup; add login if needed)
│   ├── api/
│   │   └── uploadthing/           # UploadThing: PDF upload for profiling
│   │       ├── route.ts           # createRouteHandler(router)
│   │       └── core.ts             # FileRouter with pdfUploader (4MB, pdf)
│   ├── onboarding/                # A. Smart Onboarding & Vibe Check
│   │   ├── page.tsx               # Flow: identity → UploadDropzone (CV) → Vibe Check → submit profiling
│   │   └── processing/            # Waiting for ProfilingWorkflow (poll status_url)
│   │       └── page.tsx
│   └── (dashboard)/               # Protected routes (sidebar layout)
│       ├── layout.tsx             # Sidebar + user context
│       ├── overview/              # C. Active runs & stats (Run table, polling)
│       ├── profile/               # C. Master Identity (user + profile_text / vibe)
│       └── matches/               # B. Match Catalog
│           └── [id]/              # B. Detail: CV + Cover Letter + application_link
├── components/
│   ├── chat/                      # Vercel AI SDK chat (vibe check)
│   ├── matches/                   # MatchCard, PDFViewer, ActionPanel
│   ├── layout/                    # Sidebar, UserNav, GlobalSearch
│   └── ui/                        # Shadcn (existing: button, card, form, input, label, separator)
├── hooks/
│   ├── useRunStatus.ts            # SSE via EventSource for real-time run status (Progress Stepper)
│   └── useVibeChat.ts             # AI SDK wrapper for vibe check
├── lib/
│   ├── auth.ts                    # Better Auth config (existing)
│   ├── auth-client.ts             # createAuthClient (existing)
│   ├── prisma.ts                  # Prisma singleton (existing)
│   └── utils.ts                   # Tailwind etc. (existing)
├── actions/
│   ├── workflow.ts                # Server Actions: triggerProfiling, triggerJobSearch, from-profile (API_KEY server-side only)
│   └── user.ts                    # Server Actions: profile updates (e.g. location)
├── services/
│   ├── workflow.service.ts        # Optional: URL/params helpers; actual POST calls go through Server Actions
│   └── status.service.ts          # SSE stream URL or GET status fallback for run status
├── store/
│   └── useOnboardingStore.ts      # Zustand store with persist(sessionStorage) for identity + basic_info (survives refresh)
├── types/
│   ├── db.d.ts                    # Prisma types (generated or hand-maintained)
│   └── workflow.ts                # API request/response shapes
└── proxy.ts                       # Network boundary: optimistic auth, routing (see §3.2)
```

**Note:** In Next.js 16+, **`middleware.ts` is deprecated** in favour of **`proxy.ts`**. The exported function must be `export function proxy(request: NextRequest)`. See [§3.2 Route protection (proxy.ts)](#32-route-protection-proxyts) and [§8 Routing & network architecture](#8-routing--network-architecture-nextjs-16).

---

## 3. Critical Implementation Reminders

### 3.1 Prisma — Read-Only Mode

- **Do not** run `prisma migrate` or `prisma db push`. Schema and migrations are owned by **Alembic** in the backend.
- Use Prisma only for **introspection** and **reads** (and any documented, limited writes such as `user.last_used_at` if agreed).
- Keep `schema.prisma` in sync via **introspection** from the existing DB after backend migrations.

### 3.2 Route Protection (proxy.ts)

- In Next.js 16+, use **`proxy.ts`** (not `middleware.ts`) as the **network boundary**. Location: `frontend/proxy.ts`. Export: `export function proxy(request: NextRequest)`.
- **Optimistic auth only:** Check for the **Better Auth session cookie** (`better-auth.session-token`) presence. Do **not** run deep business logic or database session checks here.
- Redirect unauthenticated users from protected paths (e.g. `/dashboard`, `/onboarding`) to sign-in (e.g. `/sign-in?callbackUrl=...`). Allow `(auth)`, public API routes, and static assets.
- **Deep session verification** (DB checks) belongs in the **Data Access Layer**: Server Components and Server Actions using the Prisma reader. Use `proxy.ts` only for redirecting signed-out users from private paths.
- **Migration:** Run `npx @next/codemod@canary middleware-to-proxy` or manually rename `middleware.ts` to `proxy.ts` and change the exported function name to `proxy`.
- Full example and Caddy alignment: see [§8 Routing & network architecture](#8-routing--network-architecture-nextjs-16).

### 3.3 Better Auth behind Caddy: trustHost

- When Next.js runs behind **Caddy** (or any reverse proxy), Better Auth must treat the incoming host as trusted so redirect URLs use the public domain, not `localhost`.
- In **`lib/auth.ts`**, set **`advanced: { trustHost: true }`** in the Better Auth config. Without this, redirects after Google login may point to `http://localhost:3000` instead of your public VPS domain.

### 3.4 Environment Variables

| Variable | Purpose | Note |
|----------|---------|------|
| `BETTER_AUTH_URL` | Server-side Better Auth base URL | Must be the **public** app URL (e.g. `https://app.example.com` in prod). |
| `NEXT_PUBLIC_BETTER_AUTH_URL` | Client-side auth base URL | Same as above for browser. |
| `DATABASE_URL` | Prisma connection | Use the **limited-privilege** user (`job_agent_ui`). Never use the backend admin user. |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL | **Must include the `/api/v1` prefix** so Caddy routes match (e.g. `https://api.example.com/api/v1` or same host with path). |
| `API_KEY` | FastAPI API key | Send via `X-API-Key` or `Authorization: Bearer` when calling FastAPI (prefer server-side only). |
| `UPLOADTHING_TOKEN` | UploadThing SDK | Token for UploadThing file storage (get from [UploadThing dashboard](https://uploadthing.com)); required for PDF upload in onboarding. |

### 3.5 PDF Rendering (Tailored CV)

- **Tailored CV URL** comes from **`artifacts.cv`** (JSON). Backend stores: `{ "pdf_url": "https://..." }`. Use `artifact.cv?.pdf_url` for the PDF link.
- Render with a standard viewer: e.g. **`@react-pdf/renderer`** for generation, or **`react-pdf`** / **PDF.js** for viewing, or a simple **`<iframe src={url} />`** for external URLs. Choose based on whether the URL is same-origin or CORS-friendly.

### 3.6 Backend Status: SSE (Primary) and Polling (Fallback)

- **Primary:** Real-time status is delivered via **SSE (Server-Sent Events)** over Redis. See [§3.7 Real-time status (SSE + Redis)](#37-real-time-status-sse--redis).
- **Fallback:** Optionally implement `GET /workflow/status/{run_id}` in FastAPI (or a Next.js proxy) that reads `Run` and returns `status`, `task_id`, `completed_at`, etc., for clients that cannot use SSE or for one-off checks.

### 3.7 Real-time Status (SSE + Redis)

- **Dependency (backend):** Ensure **redis** (and optionally **redis[hiredis]** for performance) is in `pyproject.toml`. The codebase already has `redis>=5.0.0`; add `redis[hiredis]` if desired. Use **redis.asyncio** (or sync client in a thread) for the FastAPI SSE subscriber.
- **FastAPI:** Create a **StreamingResponse** endpoint (e.g. `GET /api/v1/workflow/status/{run_id}/stream` or `/workflow/status/{run_id}/stream`) that subscribes to the Redis channel **`run:status:{run_id}`**. The generator must yield SSE-formatted strings: **`data: {json}\n\n`** (double newline after each event). **SSE heartbeat:** If no real event is sent for a period, the connection can be dropped by the browser or proxy. The FastAPI generator must send a **heartbeat** every **15 seconds** when idle: yield a comment line **`: keep-alive\n\n`** (SSE comment) so the connection stays open.
- **Worker (Celery):** In **BaseWorkflow** or **BaseNode**, whenever **context.status** or the **current node** changes, **publish** a JSON payload to Redis on the channel `run:status:{run_id}`. Payload should include at least `status`, `node` (or `step`), and optional `message` / `completed_at` so the frontend can drive a Progress Stepper.
- **Frontend:** Create **`hooks/useRunStatus.ts`** using the browser’s native **EventSource** (e.g. `new EventSource(sseUrl)`). Parse incoming `data:` lines as JSON and update state. Use this stream to drive a **Progress Stepper** in the Dashboard (e.g. on `/onboarding/processing` and `/dashboard/overview`). Close the EventSource when status is `completed` or `failed`, or on component unmount.
- **Caddy (API domain):** SSE connections are long-lived. Ensure the **reverse_proxy** for the API has a long **read timeout** (e.g. Caddy: **`header_timeout 10m`** or equivalent) so the Progress Stepper does not suddenly stop when the proxy closes the connection. If SSE updates feel delayed, add **`proxy_buffering off`** (or Caddy's equivalent, e.g. `flush_interval -1`) for the API block.

---

## 4. Feature-by-Feature Implementation Notes

### A. Smart Onboarding & Vibe Check

**Flow:** Sign in (Google OAuth) → Onboarding page → Confirm identity (name, email, location) → **Upload CV (PDF via UploadThing)** → Vibe Check chat → Cultural Persona (2–3 paragraphs) → Submit to profiling workflow → Redirect to processing page.

**PDF upload (UploadThing)**

- **Tooling:** Use [UploadThing](http://docs.uploadthing.com/getting-started/appdir) for file storage so the profiling backend receives **public CV URLs**.
- **Config:** Set up **`app/api/uploadthing/route.ts`** and **`app/api/uploadthing/core.ts`**. In `core.ts`, define a **FileRouter** with a **`pdfUploader`** route that limits files to **4MB** and type **pdf**. Export the router type for the client. In `route.ts`, use **`createRouteHandler`** from `uploadthing/next` with that router and export **GET** and **POST**. Add **`UPLOADTHING_TOKEN`** to `.env` (from [UploadThing dashboard](https://uploadthing.com)).
- **Component:** Use the **UploadDropzone** from `@uploadthing/react` (or a re-export with types from `core.ts`) in **`app/onboarding/page.tsx`**. Mount it on the onboarding step where the user adds their CV (e.g. after identity, before or after Vibe Check).
- **State:** On successful upload, use **`onClientUploadComplete`**. In the callback, take the returned file(s) and push each **`file.url`** (the public link) into the **`cv_urls`** array in **useOnboardingStore** (Zustand). The store already has `cv_urls`; ensure the store exposes an action like `addCvUrl(url)` or you update `cv_urls` from the callback.
- **Final action:** When the user submits the profiling workflow (Server Action **triggerProfiling**), pass **`cv_urls`** from **useOnboardingStore** in the payload to the FastAPI backend. The backend expects `cv_urls` as a list of public URLs; UploadThing returns stable URLs per file.

**Identity refinement**

- Read **session** from Better Auth (e.g. `authClient.getSession()` or server-side equivalent).
- Pre-fill **name** and **email** from session; allow user to edit and add **location**.
- Persist location (and any profile fields you own) via Prisma on `user` (e.g. `location`) if the backend schema allows writes for the UI user; otherwise only send them in the profiling payload.

**Vibe Check chat**

- Use **Vercel AI SDK** (e.g. `useChat`) in a dedicated chat UI.
- **Goal:** Elicit preferences on work culture, team size, remote/hybrid.
- **Output:** A 2–3 paragraph **Cultural Persona** summary (plain text or structured). Store it in **Zustand** with **persist (sessionStorage)** so a page refresh during the chat does not wipe the summary. See [Zustand persistence](#zustand-persistence-for-onboarding) below.

**Workflow trigger (Server Actions)**

- Workflow triggers (e.g. **triggerProfiling**) are mutations that start a process. In Next.js 16+, call the FastAPI backend from **Server Actions** only, so **API_KEY** stays server-side and the browser never sees it.
- **`actions/workflow.ts`:** Export **Server Actions** that call `POST {API_URL}/workflow/profiling`, `/workflow/job-search`, `/workflow/job-search/from-profile` with `X-API-Key` or `Authorization: Bearer` using `API_KEY` from env. Return typed response (run_id, status_url, etc.). **`services/workflow.service.ts`** can remain as a helper for URL/params if needed; the actual `fetch` with API_KEY must run in Server Actions.
- **Endpoint:** `POST {API_URL}/workflow/profiling` (called from Server Action). Body: `name`, `email`, `location`, `basic_info?`, `cv_urls`. Response: `202` with `run_id`, `task_id`, `status`, `status_url`, `estimated_completion_time`.
- After the Server Action returns, redirect to **`/onboarding/processing?run_id=...`**. Use **useRunStatus** (SSE via EventSource) to stream status and drive a Progress Stepper; when status is `completed` or `failed`, redirect to dashboard or show error.

**Zustand persistence for onboarding**

- **`store/useOnboardingStore.ts`:** Create a Zustand store for onboarding state (name, email, location, **basic_info** from Vibe Check, **cv_urls**). Include **cv_urls** as an array of strings (public URLs from UploadThing). Expose an action to append a URL (e.g. `addCvUrl(url)`) for use in **onClientUploadComplete**. Use the **`persist`** middleware with **`storage: sessionStorage`** so that if the user accidentally refreshes during step 2 (Vibe Check), the Cultural Persona summary (and cv_urls) is not lost. Clear or hydrate the store as needed when moving between steps or after successful profiling.

---

### B. Match Catalog (Execution Layer)

**Data source (Prisma, read-only)**

- **Tables:** `matched_jobs`, `job_postings`, `artifacts`.
- **Relations (from schema):**  
  - `matched_jobs` → `job_postings` (job title, company, description, etc.)  
  - `matched_jobs` → `artifacts` (one-to-one) for CV and cover letter.
- **Key fields:**  
  - **Match:** `matched_jobs.reason` (AI reasoning), `matched_jobs.is_match`, `matched_jobs.application_link` (JSON: e.g. `{ "via", "link" }`).  
  - **Job:** `job_postings.title`, `job_postings.company_name`, `job_postings.location`, etc.  
  - **Artifacts:** `artifacts.cover_letter` (JSON/text for cover letter), `artifacts.cv` (JSON with **`pdf_url`** for tailored CV).

**UI behaviour**

- **List:** Grid or list of matches; each item shows job title, company, **reason**, and optionally a match indicator (e.g. `is_match`; “Match score” can be added later if the backend exposes it).
- **Detail (`matches/[id]`):**  
  - Side-by-side or tabbed: **Tailored CV** (render from `artifacts.cv.pdf_url`) and **Cover Letter** (render `artifacts.cover_letter` JSON or text).  
  - **Direct link:** “Apply” button using `application_link.link` (with fallback if structure differs).
  - **PDF preview:** Use **`sandbox="allow-scripts allow-same-origin"`** on the PDF **`<iframe>`** for security.
  - **Download/Print:** Implement a “Download” or “Print” button using a hidden **`<a href={pdf_url} download>`** so the user can save or print the tailored CV (some browsers block iframe downloads).
  - **Security check (handoff):** Confirm whether `pdf_url` in the DB are **signed S3 URLs** (time-limited) or **public URLs**; if signed, do not cache beyond validity.

**Queries**

- Fetch matches for the current user: filter `matched_jobs` by `user_id` (from session), include `job_postings` and `artifacts`. Use Prisma `findMany` with `include: { job_postings: true, artifacts: true }`.
- Ensure **only** the `job_agent_ui` user is used for Prisma; no schema changes.

---

### C. Real-time Dashboard & History

**Async monitoring (Run table + SSE)**

- **Data:** `runs` table: `id`, `status`, `task_id`, `user_id`, `job_search_id`, `completed_at`, etc.
- **Real-time:** Use **SSE** via Redis channel `run:status:{run_id}`. FastAPI exposes a **StreamingResponse** endpoint that subscribes to this channel and yields `data: {json}\n\n`. Workers publish status/node updates to Redis. See [§3.6 Real-time status (SSE + Redis)](#36-real-time-status-sse--redis).
- **Hook:** **`hooks/useRunStatus.ts`** — accept `runId` (or SSE URL). Open **EventSource** to the stream URL, parse `data:` events as JSON, update state (e.g. `status`, `node`, `message`). Drive a **Progress Stepper** in the Dashboard (e.g. overview and onboarding/processing). Close EventSource when `status` is `completed` or `failed`, or on unmount. Optional fallback: poll `GET /workflow/status/{run_id}` if SSE is unavailable.

**Master Profile**

- **Source:** `user` table: `name`, `email`, `image`, `location`, **`profile_text`** (from CV + backend), and optionally the stored “vibe” summary if you persist it (e.g. in `profile_text` or a dedicated field if added later).
- **Page:** `(dashboard)/profile/page.tsx` — visual overview of this “Master Identity” (editable or read-only as per product).

---

## 5. Suggested Implementation Order

1. **Types and services**  
   - `types/workflow.ts` (profiling, job-search, status response).  
   - `services/workflow.service.ts` (profiling + job-search triggers).  
   - `services/status.service.ts` (SSE stream URL or fetch status by run_id for fallback).

2. **Auth and protection**  
   - **proxy.ts:** Implement `frontend/proxy.ts` with optimistic cookie check; protect `/dashboard` (and `/onboarding` if desired), redirect to `/sign-in` when unauthenticated. See [§8 Routing & network architecture](#8-routing--network-architecture-nextjs-16).  
   - Ensure `(auth)` and public routes are accessible. Deep session verification in Server Components/Actions with Prisma.

3. **Onboarding**  
   - Onboarding layout and identity step (name, email, location from session).  
   - **PDF upload:** UploadThing (`app/api/uploadthing/route.ts` + `core.ts`, **pdfUploader** 4MB/pdf); **UploadDropzone** in `app/onboarding/page.tsx`; **onClientUploadComplete** → append **file.url** to **cv_urls** in **useOnboardingStore**.  
   - Vibe Check: Vercel AI SDK chat → Cultural Persona summary.  
   - Submit to `POST /workflow/profiling` (Server Action) with **cv_urls** from store; redirect to `/onboarding/processing`.  
   - Processing page: use **useRunStatus** (SSE via EventSource) to drive a Progress Stepper; on completion, redirect to dashboard.

4. **Dashboard shell**  
   - `(dashboard)/layout.tsx` with sidebar and user context.  
   - Overview page: list active runs (from `runs` by `user_id`); use **useRunStatus** (SSE) for in-progress runs and a **Progress Stepper**.  
   - Profile page: Master Identity from `user` (+ vibe summary if stored).

5. **Match catalog**  
   - Matches list (Prisma: `matched_jobs` + `job_postings` + `artifacts`).  
   - Detail page: CV (`artifacts.cv.pdf_url`), Cover Letter (`artifacts.cover_letter`), `application_link`.  
   - PDF viewer component and link to external application.

6. **Polish**  
   - Error states, loading states, and empty states for onboarding, dashboard, and matches.

---

## 6. API Contract Summary (Backend Reference)

- **POST /workflow/profiling**  
  - Body: `name`, `email`, `location`, `cv_urls[]`, `basic_info?`.  
  - Response: `202` — `run_id`, `task_id`, `status`, `status_url`, `estimated_completion_time`.

- **POST /workflow/job-search**  
  - Body: Job search context (see FastAPI).  
  - Response: `202` — same shape as above.

- **POST /workflow/job-search/from-profile**  
  - Body: `user_id` (UUID).  
  - Response: `202` — message, user_id, location, job_titles_count, job_titles.

- **GET /workflow/status/{run_id}**  
  - Optional (fallback). Return Run fields: `status`, `task_id`, `completed_at`, `error_message`, etc.

- **GET /workflow/status/{run_id}/stream** (or under `/api/v1/...`)  
  - **SSE endpoint.** Subscribe to Redis channel `run:status:{run_id}`; yield `data: {json}\n\n` for each event. Used by **useRunStatus** and the Progress Stepper.

---

## 7. Prisma Schema Snippets (Reference)

- **User:** `id`, `name`, `email`, `location`, `profile_text`, `suggested_job_titles`, `source_pdfs`, `references`, …
- **Run:** `id`, `status`, `task_id`, `user_id`, `job_search_id`, `completed_at`, `error_message`, …
- **matched_jobs:** `id`, `job_search_id`, `job_posting_id`, `run_id`, `user_id`, `is_match`, `reason`, `application_link` (Json), …
- **job_postings:** `id`, `title`, `company_name`, `location`, `description`, …
- **artifacts:** `id`, `matched_job_id`, `cover_letter` (Json), `cv` (Json — use **`cv.pdf_url`** for tailored CV PDF).

---

## 8. Routing & Network Architecture (Next.js 16+)

### 8.1 The core shift: middleware.ts → proxy.ts

In **Next.js 16+**, `middleware.ts` is deprecated. Its successor is **proxy.ts**.

- **Purpose:** **proxy.ts** is the **network boundary**. It should handle lightweight routing, rewrites, and **optimistic auth checks** (e.g. checking for cookie presence), not deep business logic or database sessions.
- **Location:** `frontend/proxy.ts` (replaces `frontend/middleware.ts`).
- **Naming:** The exported function must be **`export function proxy(request: NextRequest)`**.
- **Migration:** Run **`npx @next/codemod@canary middleware-to-proxy`** or manually rename `middleware.ts` to `proxy.ts` and update the function name to `proxy`.

**Auth philosophy:** Move deep session verification (DB checks) into the **Data Access Layer** (Server Components / Server Actions) using the Prisma reader. Use **proxy.ts** only for redirecting signed-out users from private paths (optimistic check).

### 8.2 Example: proxy.ts implementation

```ts
// frontend/proxy.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Optimistic check: does the Better Auth session cookie exist?
  const sessionCookie = request.cookies.get("better-auth.session-token");

  // Protect internal routes (Dashboard, etc.)
  if (pathname.startsWith("/dashboard") && !sessionCookie) {
    const url = request.nextUrl.clone();
    url.pathname = "/sign-in";
    url.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(url);
  }

  // Optional: protect /onboarding for signed-in-only flow
  // if (pathname.startsWith("/onboarding") && !sessionCookie) { ... }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

Ensure **proxy.ts** does not run on static assets or API routes that Caddy handles. Pass through **X-Forwarded-Proto** (Caddy sets this by default) so Better Auth knows the site is on HTTPS when SSL is terminated at Caddy.

### 8.3 Caddy: the traffic controller

On the VPS, **Caddy** does the first layer of routing so traffic intended for the Python backend never hits Next.js and vice versa.

**Caddyfile (draft):**

```caddyfile
{$DOMAIN} {
    # 1. API: Python Backend (Alembic/FastAPI)
    # Path prefix separates business logic
    handle /api/v1/* {
        reverse_proxy localhost:8000 {
            # Long-lived SSE: prevent proxy from closing the connection
            header_timeout 10m
            # If SSE updates feel delayed, disable buffering:
            # flush_interval -1
        }
    }

    # 2. Auth: Better Auth (must go to Next.js)
    handle /api/auth/* {
        reverse_proxy localhost:3000
    }

    # 3. Frontend: catch-all (Next.js App)
    handle {
        reverse_proxy localhost:3000
    }
}
```

**Guardrail:** If SSE updates from the API feel delayed, add **`proxy_buffering off`** (or Caddy’s equivalent, e.g. `flush_interval -1` in reverse_proxy) for the API block so the stream is not buffered.

### 8.4 Alignment with application URLs

- **BETTER_AUTH_URL** must be the **public domain** (e.g. `https://app.example.com`). Same for **NEXT_PUBLIC_BETTER_AUTH_URL** on the client.
- **NEXT_PUBLIC_API_URL** should **include the `/api/v1` prefix** so frontend and Caddy routing match (e.g. `https://api.example.com/api/v1` or `https://app.example.com/api/v1` if the API is under the same domain).
- **Security headers:** Caddy sets **X-Forwarded-Proto**, **X-Forwarded-For**, etc. by default. Ensure the Next.js app and Better Auth receive these so HTTPS and client IP are correct.

---

## 9. Architect's Final Polish Notes (Handover for Agent)

Copy-paste summary for the Cursor Agent:

> **Architect's Final Polish Notes:**
> 1. **Auth Trust:** In `lib/auth.ts`, set `advanced.trustHost = true` to support the Caddy reverse proxy.
> 2. **Zustand Persistence:** Use `persist` (sessionStorage) for the onboarding store (`useOnboardingStore`) to prevent data loss on refresh during the Vibe Check.
> 3. **SSE Heartbeat:** The FastAPI SSE generator must yield a `: keep-alive` comment every 15s when idle to prevent Caddy/browser timeouts.
> 4. **Server Actions:** Use Next.js Server Actions for all `POST` calls to the FastAPI backend (workflow triggers). Keep the `API_KEY` env var private to the server.
> 5. **PDF Iframe:** Use `sandbox="allow-scripts allow-same-origin"` on the PDF preview `<iframe>` for security. Provide a "Download/Print" button via a hidden `<a download>` (or equivalent) because some browsers block iframe downloads.

---

## 10. Summary Checklist for Cursor

- [ ] **`proxy.ts`** is implemented with optimistic cookie check; protected routes redirect to sign-in when unauthenticated.
- [ ] **SSE** Progress Stepper is active on **`/dashboard/overview`** and **`/onboarding/processing`**; backend sends heartbeat every 15s; Caddy has long read timeout for API.
- [ ] **Prisma 7** is used in Server Components for the Match Catalog (and profile/overview reads); no migrate/db push.
- [ ] **Vercel AI SDK** generates the **`basic_info`** (Cultural Persona) summary; it is stored in Zustand with sessionStorage persist so refresh does not lose it.
- [ ] **Workflow triggers** (profiling, job-search, from-profile) are invoked via **Server Actions** only; API_KEY is never sent to the client.
- [ ] **Better Auth** has `advanced.trustHost = true` in `lib/auth.ts`.
- [ ] **PDF upload (UploadThing):** `app/api/uploadthing/route.ts` + `core.ts` with **pdfUploader** (4MB, pdf); **UploadDropzone** in onboarding; **onClientUploadComplete** saves **file.url** into **cv_urls** in **useOnboardingStore**; final submission includes **cv_urls** from store in the profiling payload.

---

This guideline is a first draft. Adjust ordering and file names to match your repo conventions and any new backend contracts (e.g. status endpoint and match score fields).
