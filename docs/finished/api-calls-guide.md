# API Calls Guide

Simple guide to calling the Job Agent API from the command line or any HTTP client.

---

## Base URL and authentication

| Environment | Base URL |
|-------------|----------|
| **Production** | `https://api.profilescreens.com` (or your API domain from `.env`) |
| **Local (dev)** | `http://localhost:8000` |

**Authentication:** All endpoints except `/health` require an API key.

- **Header (recommended):** `X-API-Key: YOUR_API_KEY`
- **Alternative:** `Authorization: Bearer YOUR_API_KEY`

Use the value of `API_KEY` or `JOB_LAND_API_KEY` from your `.env`.

---

## 1. Health check (no auth)

Check that the API is up.

```bash
curl "https://api.profilescreens.com/health"
```

**Expected:** `{"status":"healthy"}`

---

## 2. Root (protected)

Confirm API version; requires API key.

```bash
curl -H "X-API-Key: YOUR_API_KEY" "https://api.profilescreens.com/"
```

**Expected:** `{"message":"Job Agent API","version":"1.0.0"}`

---

## 3. Profiling workflow

Create a user profile from a name, email, location, and CV/PDF URLs. The backend downloads the PDFs, extracts content, and builds a structured profile (saved in the DB). Runs asynchronously (Celery).

**Endpoint:** `POST /workflow/profiling`

**Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | User's name |
| `email` | string | Yes | User's email |
| `location` | string | Yes | Preferred job search location (e.g. `"Hong Kong"`) |
| `basic_info` | string | No | Optional short bio or notes |
| `cv_urls` | array of strings | Yes | Public URLs to CV/PDF files (`http://` or `https://`) |

**Example:**

```bash
curl -X POST "https://api.profilescreens.com/workflow/profiling" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "name": "Jane Doe",
    "email": "jane@example.com",
    "location": "Hong Kong",
    "basic_info": "Optional notes.",
    "cv_urls": ["https://example.com/path/to/cv.pdf"]
  }'
```

**Expected (202 Accepted):**

```json
{
  "run_id": "uuid-of-run",
  "execution_id": "uuid-of-execution",
  "task_id": "celery-task-id",
  "status": "pending",
  "status_url": "/workflow/status/<run_id>",
  "estimated_completion_time": "3-5 minutes"
}
```

Use `run_id` to check status (e.g. poll `GET /workflow/status/<run_id>` if that endpoint is implemented). Monitor tasks in Flower: `https://flower.profilescreens.com`.

---

## 4. Job search workflow (from profile)

Trigger job searches for each of a profile’s suggested job titles. Requires an existing profile (run profiling first). Runs asynchronously (Celery).

**Endpoint:** `POST /workflow/job-search/from-profile`

**Body (JSON):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_id` | UUID | Yes | ID of the profile (from profiling workflow result / DB) |
| `num_results` | integer | No | Jobs to fetch per search (default from config) |
| `max_screening` | integer | No | Max jobs to screen per search (default from config) |

**Example:**

```bash
curl -X POST "https://api.profilescreens.com/workflow/job-search/from-profile" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "profile_id": "PROFILE_UUID_HERE",
    "num_results": 10,
    "max_screening": 5
  }'
```

**Expected (202 Accepted):**

```json
{
  "message": "Job searches initiated via Celery",
  "profile_id": "uuid",
  "location": "Hong Kong",
  "job_titles_count": 3,
  "job_titles": ["Software Engineer", "Backend Developer", "…"]
}
```

---

## 5. Job search workflow (raw context)

Run a single job search with explicit query and location. For most use cases, prefer **from-profile** after profiling.

**Endpoint:** `POST /workflow/job-search`

**Body (JSON):** Same shape as `JobSearchWorkflow.Context` (e.g. `query`, `location`, `profile_id`, `num_results`, `max_screening`). See `src/workflow/base_context.py` and API code for full fields.

**Example (minimal):**

```bash
curl -X POST "https://api.profilescreens.com/workflow/job-search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "query": "Software Engineer",
    "location": "Hong Kong",
    "num_results": 10,
    "max_screening": 5
  }'
```

**Expected (202 Accepted):** JSON with `run_id`, `execution_id`, `task_id`, `status`, `status_url`, `estimated_completion_time`.

---

## Quick reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Health check |
| GET | `/` | Yes | API info |
| POST | `/workflow/profiling` | Yes | Create profile from CV URLs |
| POST | `/workflow/job-search/from-profile` | Yes | Job searches from profile’s job titles |
| POST | `/workflow/job-search` | Yes | Single job search (raw context) |

Replace `YOUR_API_KEY` and the base URL with your values. For local dev, use `http://localhost:8000`. For production, use your API domain (e.g. `https://api.profilescreens.com`).
