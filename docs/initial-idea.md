# JobLand Assistant: Vision and Architecture

## Goal
To simplify the job search process and maximize application quality by automating research and material preparation. The system transforms a broad search into a high-fidelity "application package" (Tailored CV, Cover Letter, and Research Report) sent directly to the user for final review.

## Core Workflow

1.  **Discovery (Search)**: Automate multi-engine searches (SerpAPI, Exa) to find fresh openings.
2.  **Extraction (Profile)**: Use `Docling` to parse the user's master CV/LinkedIn and create a "Living Profile".
3.  **Screening (Matcher)**: 
    *   A "ruthless" AI agent filters jobs by likelihood of landing.
    *   Provides a match score (0-100), identifying specific skill gaps and deal-breakers.
4.  **Intelligence (Researcher)**: For high-score jobs, a deep-dive agent researches the company's culture, mission, and recent news via Exa.
5.  **Fabrication (Generator)**:
    *   **Tailored CV**: Generate a full CV based on a Markdown/LaTeX template, re-prioritizing bullet points and keywords to match the specific job requirements.
    *   **Cover Letter**: Draft a personalized letter connecting the user's unique experience to the company's specific needs found during research.
6.  **Delivery (Notifier)**: Bundle the materials and send them to the user via Email (Nylas or Gmail API).

---

## Technical Modules

### 1. Search Service (`SerpApiJobsService`)
*   Current implementation handles Google Jobs pagination and factory instantiation.
*   Future: Support for additional job engines.

### 2. Profile Engine
*   **Tools**: `Docling` for high-fidelity PDF parsing.
*   **Role**: Converts the user's master experience into a structured data format for the Matcher.

### 3. High-Fidelity Matcher (`JobScreeningAgent`)
*   **Output**: `JobScreeningOutput` (Match Score, Probability, Reasons, Missing Skills).
*   **Role**: Only triggers the expensive research/generation phase for "High" probability matches.

### 4. Company Research Agent
*   **Search**: Uses Exa's `search` and `get_contents` to find culture and news.
*   **Output**: A concise "Company Dossier" used to inform the Generator.

### 5. Application Material Generator
*   **Engine**: `Jinja2` for template rendering.
*   **Logic**: Maps user experiences to job requirements to generate the most relevant CV possible.

### 6. Email Delivery Service
*   **Integration**: Nylas or Gmail API.
*   **Action**: Sends the application package to the user's inbox.

---

## Future Roadmap
*   **Interview Prep**: Generate a "Cheat Sheet" for the interview based on the company research.
*   **Application Tracking**: Automatically log which jobs were generated in a local DB or Google Sheets.


## Refined Architecture: Event-Driven Workflow Orchestration with State Persistence

### Critical Analysis of Initial Design

The initial multi-stage orchestration design has several **critical flaws**:

#### ❌ **Problems Identified:**

1. **Profile "Independence" is Misleading**: Profile is cacheable, not truly parallel. It's a prerequisite for matching, so it must complete before matching can start.

2. **Missing State Persistence**: No way to resume long-running workflows if they crash mid-execution (e.g., during company research).

3. **Fan-In Timing Problem**: Unclear when to collect results. Do we wait for all jobs? What if some fail or take 10x longer?

4. **No Rate Limiting/Backpressure**: Parallel processing could hit API rate limits (SerpAPI, Exa, LLM APIs) without throttling.

5. **Inefficient Context Passing**: Passing `user_profile: str` in contexts is wasteful. Should use `user_profile_id: UUID` and load on demand.

6. **No Error Recovery**: No retry strategy, dead letter queue, or partial failure handling.

7. **Orchestrator Doing Too Much**: Mixes coordination, execution, and persistence concerns.

8. **Missing Database Model**: `ApplicationPackage` mentioned but doesn't exist in schema.

9. **No Workflow Engine**: Status field suggests state machine, but no actual engine manages transitions.

10. **Batch Completion Ambiguity**: How do we know when a batch is "complete"? Race conditions possible.

### Refined Architecture: Event-Driven with State Machine

The refined architecture uses **Event-Driven Orchestration** with **State Persistence** and **Workflow Engine**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW ORCHESTRATOR                            │
│  (Coordinates stages, manages state transitions, handles events)   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: PROFILE LOADING                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ ProfileService.load_or_build()                               │  │
│  │  - Check cache by (name, email)                              │  │
│  │  - If missing: parse PDFs → build profile → save            │  │
│  │  - Returns: profile_id (UUID)                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: JOB DISCOVERY                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ DiscoveryService.search()                                    │  │
│  │  - Query SerpAPI with rate limiting                          │  │
│  │  - Save JobSearch + JobPostings to DB                        │  │
│  │  - Returns: job_search_id, job_posting_ids[]                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: JOB MATCHING                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ MatchingService.screen_jobs()                                │  │
│  │  - Load profile by profile_id                                  │  │
│  │  - Screen jobs with rate limiting                             │  │
│  │  - Save MatchedJob records                                    │  │
│  │  - Returns: matched_job_ids[] (only is_match=True)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: BATCH CREATION                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ BatchService.create_batch()                                   │  │
│  │  - Create Batch record with status='pending'                  │  │
│  │  - Create ApplicationPackage for each matched_job             │  │
│  │    with status='pending'                                      │  │
│  │  - Enqueue job processing tasks to queue                      │  │
│  │  - Returns: batch_id                                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 5: PARALLEL JOB PROCESSING                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ JobProcessor (Worker Pool with Rate Limiting)                 │  │
│  │                                                               │  │
│  │  For each ApplicationPackage:                                │  │
│  │    1. Update status='researching'                             │  │
│  │    2. CompanyResearchService.research()                       │  │
│  │       - Rate limit: max 10 concurrent Exa API calls          │  │
│  │       - Save research to ApplicationPackage                    │  │
│  │                                                               │  │
│  │    3. Update status='generating'                              │  │
│  │    4. MaterialGenerator.generate()                            │  │
│  │       - Load profile by profile_id                            │  │
│  │       - Generate CV + Cover Letter                            │  │
│  │       - Save to ApplicationPackage                             │  │
│  │                                                               │  │
│  │    5. Update status='completed'                               │  │
│  │    6. Emit event: 'package.completed'                         │  │
│  │                                                               │  │
│  │  On failure:                                                  │  │
│  │    - Update status='failed'                                   │  │
│  │    - Log error                                                 │  │
│  │    - Retry up to 3 times with exponential backoff             │  │
│  │    - Emit event: 'package.failed'                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 6: BATCH COMPLETION                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ BatchCompletionService (Event Listener)                       │  │
│  │                                                               │  │
│  │  Listens for 'package.completed' events                      │  │
│  │                                                               │  │
│  │  When all packages in batch are completed:                   │  │
│  │    1. Update Batch.status='completed'                        │  │
│  │    2. Emit event: 'batch.completed'                          │  │
│  │                                                               │  │
│  │  Timeout handling:                                            │  │
│  │    - After 1 hour, mark remaining as 'timeout'               │  │
│  │    - Send partial batch if >= 50% complete                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 7: EMAIL DELIVERY                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ EmailService.send_batch() (Event Listener)                    │  │
│  │                                                               │  │
│  │  Listens for 'batch.completed' events                        │  │
│  │                                                               │  │
│  │  1. Load all ApplicationPackages for batch_id                │  │
│  │  2. Bundle materials (CV, Cover Letter, Research)            │  │
│  │  3. Send email via Nylas/Gmail API                           │  │
│  │  4. Update Batch.email_sent_at                               │  │
│  │                                                               │  │
│  │  On failure:                                                  │  │
│  │    - Retry with exponential backoff                          │  │
│  │    - Dead letter queue after 5 retries                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Database Schema Refinements

#### New Models Required:

```python
class Batch(Base):
    """Represents a batch of job applications processed together."""
    __tablename__ = "batches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_search_id = Column(UUID(as_uuid=True), ForeignKey("job_searches.id"), nullable=False)
    user_profile_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    
    status = Column(String(50), nullable=False, default="pending")  
    # pending, processing, completed, partial, failed
    
    total_packages = Column(Integer, nullable=False, default=0)
    completed_packages = Column(Integer, nullable=False, default=0)
    failed_packages = Column(Integer, nullable=False, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    email_sent_at = Column(DateTime, nullable=True)
    
    # Relationships
    application_packages = relationship("ApplicationPackage", back_populates="batch")
    job_search = relationship("JobSearch")
    user_profile = relationship("UserProfile")


class ApplicationPackage(Base):
    """Represents a complete application package for a single job."""
    __tablename__ = "application_packages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False)
    matched_job_id = Column(UUID(as_uuid=True), ForeignKey("matched_jobs.id"), nullable=False)
    user_profile_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id"), nullable=False)
    
    status = Column(String(50), nullable=False, default="pending")
    # pending, researching, generating, completed, failed, timeout
    
    # Generated materials (stored as text, can be converted to PDF later)
    company_research = Column(Text, nullable=True)
    tailored_cv = Column(Text, nullable=True)
    cover_letter = Column(Text, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    batch = relationship("Batch", back_populates="application_packages")
    matched_job = relationship("MatchedJob")
    user_profile = relationship("UserProfile")
```

### Refined Context Objects

#### 1. `ProfileLoadResult` (Immutable, Database-Backed)
```python
@dataclass(frozen=True)
class ProfileLoadResult:
    """Result of profile loading - immutable, references DB."""
    profile_id: uuid.UUID
    was_cached: bool
    # No profile text here - load from DB when needed
```

#### 2. `DiscoveryResult` (Immutable, Database-Backed)
```python
@dataclass(frozen=True)
class DiscoveryResult:
    """Result of job discovery - immutable, references DB."""
    job_search_id: uuid.UUID
    job_posting_ids: List[uuid.UUID]
    total_found: int
```

#### 3. `MatchingResult` (Immutable, Database-Backed)
```python
@dataclass(frozen=True)
class MatchingResult:
    """Result of job matching - immutable, references DB."""
    matched_job_ids: List[uuid.UUID]  # Only is_match=True
    total_screened: int
    total_matched: int
```

#### 4. `JobProcessingTask` (Task Queue Payload)
```python
@dataclass
class JobProcessingTask:
    """Task payload for job processing queue."""
    application_package_id: uuid.UUID
    matched_job_id: uuid.UUID
    user_profile_id: uuid.UUID
    batch_id: uuid.UUID
    retry_count: int = 0
```

### Key Architectural Improvements

#### 1. **State Persistence**
- All workflow state persisted to database immediately
- Can resume from any point after crash
- Status fields track progress through state machine

#### 2. **Event-Driven Completion**
- Batch completion detected via events, not polling
- Timeout handling for stuck jobs
- Partial batch delivery if some jobs fail

#### 3. **Rate Limiting & Backpressure**
```python
class RateLimitedExecutor:
    """Manages rate limits across API calls."""
    def __init__(self):
        self.exa_semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
        self.llm_semaphore = asyncio.Semaphore(5)   # Max 5 concurrent
        self.serpapi_rate_limiter = RateLimiter(max_calls=100, period=60)
```

#### 4. **Efficient Data Loading**
- Contexts only store IDs, not full data
- Lazy loading: load profile/job data only when needed
- Reduces memory footprint for parallel processing

#### 5. **Error Recovery**
```python
class RetryPolicy:
    """Configurable retry strategy."""
    max_retries: int = 3
    backoff_strategy: str = "exponential"  # exponential, linear
    retryable_errors: List[Type[Exception]] = [
        RateLimitError,
        TimeoutError,
        TransientAPIError,
    ]
```

#### 6. **Workflow Engine**
```python
class WorkflowEngine:
    """Manages state transitions and validation."""
    
    STATE_TRANSITIONS = {
        "pending": ["researching", "failed"],
        "researching": ["generating", "failed"],
        "generating": ["completed", "failed"],
        "failed": ["pending"],  # After retry
        "completed": [],  # Terminal state
    }
    
    def transition(self, package: ApplicationPackage, new_status: str):
        """Validate and execute state transition."""
        if new_status not in self.STATE_TRANSITIONS[package.status]:
            raise InvalidStateTransitionError(...)
        package.status = new_status
        # Emit event for state change
```

#### 7. **Separation of Concerns**
- **Orchestrator**: Coordinates stages, creates batches
- **Workers**: Execute job processing tasks
- **Event Listeners**: Handle completion and delivery
- **Services**: Business logic (research, generation, email)

### Implementation Strategy

#### Phase 1: Database Schema
1. Add `Batch` and `ApplicationPackage` models
2. Add status fields and relationships
3. Migration script

#### Phase 2: Refactor Contexts
1. Replace `WorkflowContext` with stage-specific result objects
2. Make contexts immutable and database-backed
3. Update all services to use new contexts

#### Phase 3: Workflow Engine
1. Implement `WorkflowEngine` for state management
2. Add state transition validation
3. Event emission system

#### Phase 4: Job Processing
1. Create `JobProcessor` worker pool
2. Implement rate limiting
3. Add retry logic
4. Queue integration (Redis/RabbitMQ or in-memory for MVP)

#### Phase 5: Batch Completion
1. Event listener for package completion
2. Batch status tracking
3. Timeout handling

#### Phase 6: Email Delivery
1. Email service with retry logic
2. Batch bundling
3. Dead letter queue

### Benefits of Refined Architecture

- ✅ **Resilience**: State persistence allows recovery from crashes
- ✅ **Scalability**: Rate limiting prevents API overload
- ✅ **Efficiency**: Lazy loading reduces memory usage
- ✅ **Observability**: Status tracking enables monitoring
- ✅ **Flexibility**: Event-driven allows async processing
- ✅ **Reliability**: Retry logic handles transient failures
- ✅ **Maintainability**: Clear separation of concerns
- ✅ **Testability**: Each component can be tested independently

---

## Celery + Redis + FastAPI Integration Architecture

### Overview

To handle task discontinuation and long-running workflows properly, we integrate **Celery** (distributed task queue) with **Redis** (message broker) and **FastAPI** (API layer). This provides:

- **Asynchronous task execution**: Long-running tasks don't block API responses
- **Task persistence**: Tasks survive worker crashes and can be retried
- **Scalability**: Multiple workers can process tasks in parallel
- **State management**: Database as source of truth, Celery for execution

### Architecture Pattern: Database as Source of Truth

**Critical Principle**: The database (PostgreSQL) is the **source of truth** for all workflow state. Celery is purely an **execution engine**.

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI (API Layer)                       │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ POST /api/v1/profiling                                │  │
│  │  1. Save files                                        │  │
│  │  2. Create UserProfile(status='pending') in DB       │  │
│  │  3. Trigger Celery task                              │  │
│  │  4. Return profile_id + status_url (202 Accepted)   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ GET /api/v1/profiling/{id}/status                     │  │
│  │  - Query DB for status (source of truth)             │  │
│  │  - Return status, progress, result_url               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Task ID (internal only)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Redis (Message Broker)                   │
│  - Task queue: celery                                      │
│  - Results: celery-task-meta-* (optional, for debugging)   │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Consume tasks
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Celery Workers                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ build_profile_task(profile_id, pdf_paths)             │  │
│  │  1. Load UserProfile from DB                         │  │
│  │  2. Update status='processing'                       │  │
│  │  3. Process PDFs                                      │  │
│  │  4. Update DB: status='completed', profile_text=... │  │
│  │  5. Call webhook if provided                         │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Updates (source of truth)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL (Source of Truth)             │
│  - UserProfile table                                        │
│  - status, profile_text, error_message, timestamps         │
│  - celery_task_id (optional, for correlation)              │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

#### 1. **Database as Source of Truth**
- ✅ All status, results, and errors stored in PostgreSQL
- ✅ API endpoints query database, not Celery state
- ✅ Celery tasks update database, not return large results
- ❌ Never rely solely on Celery `AsyncResult` for status

#### 2. **Resource IDs, Not Task IDs**
- ✅ Return `profile_id`, `batch_id`, `application_package_id` to clients
- ✅ Store `celery_task_id` in database for internal correlation
- ❌ Don't expose Celery task IDs in API responses

#### 3. **HTTP 202 Accepted Pattern**
- ✅ Return `202 Accepted` immediately when task is queued
- ✅ Provide `status_url` for polling
- ✅ Provide `result_url` that becomes available when complete

#### 4. **Idempotent Tasks**
- ✅ Tasks check database state before processing
- ✅ Safe to retry if task fails
- ✅ Can handle duplicate task execution

#### 5. **Error Handling**
- ✅ Update database status on failure
- ✅ Store error messages in database
- ✅ Use Celery retries for transient errors
- ✅ Dead letter queue for permanent failures

### API Design Pattern

```python
# Request
POST /api/v1/profiling
{
  "pdf_files": [...],
  "webhook_url": "https://client.com/webhook"  # Optional
}

# Response (202 Accepted)
{
  "profile_id": "uuid-here",
  "status": "pending",
  "status_url": "/api/v1/profiling/{profile_id}/status",
  "result_url": "/api/v1/profiling/{profile_id}"  # Available when completed
}

# Status Polling
GET /api/v1/profiling/{profile_id}/status
{
  "profile_id": "uuid-here",
  "status": "processing",  # pending, processing, completed, failed
  "progress": 45,  # Optional: 0-100
  "created_at": "2026-01-27T10:00:00Z",
  "result_url": null  # Available when status='completed'
}

# Result Retrieval
GET /api/v1/profiling/{profile_id}
{
  "profile_id": "uuid-here",
  "profile_text": "...",
  "completed_at": "2026-01-27T10:05:00Z"
}
```

### Task Structure

Each Celery task follows this pattern:

1. **Load resource from database** (using resource_id)
2. **Check current status** (idempotency check)
3. **Update status to 'processing'**
4. **Execute business logic**
5. **Update database with results**
6. **Update status to 'completed'**
7. **Call webhook if provided** (optional)

### Benefits

- ✅ **Resilience**: Tasks survive worker crashes, can be retried
- ✅ **Scalability**: Horizontal scaling with multiple workers
- ✅ **Observability**: Database provides complete audit trail
- ✅ **API Simplicity**: Clients don't need to understand Celery
- ✅ **Flexibility**: Can switch task queue implementation without API changes
- ✅ **Debugging**: Database + Celery logs provide full traceability

### Integration Points

1. **FastAPI → Celery**: Trigger tasks via `task.delay()` or `task.apply_async()`
2. **Celery → Database**: Tasks update database status and results
3. **FastAPI → Database**: API queries database for status and results
4. **Celery → Webhooks**: Tasks call webhooks on completion (optional)
5. **Monitoring**: Flower for Celery, database queries for API status 