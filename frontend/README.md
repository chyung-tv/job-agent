# Job Agent Frontend

A modern, AI-powered job search and matching application built with Next.js 16. This frontend acts as the interface for the Job Agent backend, handling user onboarding, profiling, job searching, and match visualization.

## 🚀 Tech Stack

- **Framework**: [Next.js 16](https://nextjs.org/) (App Router)
- **Runtime**: [React 19](https://react.dev/)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS 4](https://tailwindcss.com/)
- **UI Components**: [Shadcn UI](https://ui.shadcn.com/) (built on [Radix UI](https://www.radix-ui.com/))
- **State Management**: [Zustand](https://zustand-demo.pmnd.rs/) (with session storage persistence)
- **Database & Auth**: [Prisma ORM](https://www.prisma.io/), [PostgreSQL](https://www.postgresql.org/), [Better Auth](https://better-auth.com/)
- **File Upload**: [UploadThing](https://uploadthing.com/)
- **AI Integration**: [Vercel AI SDK](https://sdk.vercel.ai/docs) (OpenAI & Google Gemini)
- **API Communication**: [Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations) & SSE (Server-Sent Events)

## 🏗️ Architecture

### Folder Structure

- `app/`: Next.js App Router routes and layouts.
  - `(auth)/`: Authentication pages (Sign in/Sign up).
  - `onboarding/`: The multi-step user profiling flow.
  - `dashboard/`: Main application interface for matches and searches.
  - `api/`: Route handlers for SSE proxying, auth, and file uploads.
- `actions/`: Server Actions for data mutations and triggering backend workflows.
- `components/`: React components.
  - `ui/`: Reusable primitive components (Shadcn).
  - `dashboard/`: Domain-specific dashboard components.
  - `layout/`: Shared layout components (Header, Sidebar).
- `lib/`: Core library configurations (Auth, Prisma, UploadThing, Utils).
- `services/`: Client/Server helper services for API URL construction and formatting.
- `store/`: Zustand stores for client-side state management (e.g., Onboarding).
- `types/`: Shared TypeScript interfaces and Zod schemas.
- `hooks/`: Custom React hooks (e.g., `useRunStatus` for SSE).

### Key Architectural Patterns

#### 1. Workflow Orchestration
The frontend communicates with a FastAPI backend. Since backend workflows can be long-running, the frontend uses:
- **Server Actions**: To trigger workflows (e.g., `triggerProfiling`, `triggerJobSearch`).
- **SSE Proxy**: A route handler (`app/api/workflow/status/[runId]/stream/route.ts`) that proxies Server-Sent Events from the backend to the client, allowing for real-time progress updates without CORS issues.

#### 2. Persistent Onboarding
User progress during onboarding is managed via **Zustand** with session storage persistence. This ensures that if a user refreshes the page during the multi-step "Vibe Check" or CV upload process, their progress is preserved.

#### 3. Authentication & Access Control
- **Better Auth**: Handles social and credential-based login.
- **Beta Access**: Server-side checks (using Prisma) ensure only authorized users can trigger expensive job search workflows.

## 🛠️ Key Functions

- **Onboarding Flow**:
  - `Identity`: Basic user info collection.
  - `Vibe Check`: An AI-powered chat interface to understand user's cultural persona.
  - `Uploads`: CV/Resume upload via UploadThing.
  - `Review`: Confirmation of all collected data before processing.
- **Profiling**: Automating the extraction of user data from CVs and chat logs using backend workflows.
- **Job Search & Matching**:
  - Triggering search runs based on user profile.
  - Visualizing matched jobs with a detailed view including AI-generated cover letters.
- **Real-time Status**: Tracking the lifecycle of backend tasks (from "Queued" to "Completed") with visual feedback.

## 🔑 Environment Variables

The project requires several environment variables to be set in a `.env` file (usually located in the root or `frontend/` directory).

```env
# Database
DATABASE_URL="postgresql://user:pass@localhost:5432/db"

# Auth
BETTER_AUTH_SECRET="your-secret"
NEXT_PUBLIC_APP_URL="http://localhost:3000"

# Backend API
NEXT_PUBLIC_API_URL="http://localhost:8000"
API_KEY="your-backend-api-key"

# UploadThing
UPLOADTHING_SECRET="sk_live_..."
UPLOADTHING_APP_ID="your-app-id"

# AI
OPENAI_API_KEY="sk-..."
GOOGLE_GENERATIVE_AI_API_KEY="your-key"
```

## 🏃 Getting Started

### Prerequisites

- Node.js 20+
- A running PostgreSQL instance
- Backend API running (for full functionality)

### Installation

```bash
cd frontend
npm install
```

### Development

The project uses `dotenv-cli` to load environment variables from the parent directory's `.env` file during development.

```bash
npm run dev
```

### Building

```bash
npm run build
npm start
```

## 🧪 Development Progress

This project is currently in **active development**.
- [x] Authentication & Beta Access logic
- [x] Multi-step Onboarding flow
- [x] Backend Workflow triggers (Server Actions)
- [x] Real-time Status Streaming (SSE)
- [x] Job Matches Dashboard
- [ ] Advanced Profile Editor
- [ ] Interview Prep Module
