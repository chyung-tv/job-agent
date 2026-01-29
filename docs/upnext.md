# Next Steps: Architectural Decisions & Implementation Plan

**Status**: Planning  
**Last Updated**: 2026-01-28  
**Author**: Development Team

---

## Table of Contents

1. [PDF Upload & Storage Architecture](#1-pdf-upload--storage-architecture)
2. [Job Title Suggestion Feature](#2-job-title-suggestion-feature)
3. [Multi-Run Job Search Architecture](#3-multi-run-job-search-architecture)
4. [Asynchronous API Pattern](#4-asynchronous-api-pattern)

---

## 1. PDF Upload & Storage Architecture

### 1.1 Context

The profiling workflow requires users to upload CV/PDF documents. We need a production-ready solution that:
- Handles file uploads securely
- Stores files reliably
- Provides URLs for PDF parsing
- Supports Chinese character encoding
- Scales with user growth
- Integrates cleanly with FastAPI

### 1.2 Decision

**Use AWS S3 for PDF storage with direct client upload via presigned URLs.**

### 1.3 Options Considered

#### Option A: AWS S3 (Selected)
**Pros:**
- Industry standard, battle-tested at scale
- Direct client upload via presigned URLs (reduces server load)
- Excellent durability (99.999999999% - 11 9's)
- Pay-as-you-go pricing
- Fine-grained access control (IAM policies)
- Supports large files (up to 5TB per object)
- Global CDN available via CloudFront
- Well-documented Python SDK (boto3)

**Cons:**
- Requires AWS account setup
- Slightly more complex initial configuration
- Need to manage IAM credentials securely

**Cost:** ~$0.023/GB/month storage + $0.005/1000 requests

#### Option B: Supabase Storage
**Pros:**
- S3-compatible API (can switch to S3 later)
- Built-in CDN and image optimization
- Row-level security policies
- Simple integration if already using Supabase
- Good free tier

**Cons:**
- Vendor lock-in to Supabase ecosystem
- Less flexible than native S3
- May need to migrate if requirements change

**Cost:** Free tier: 1GB storage, then $0.021/GB/month

#### Option C: Cloudinary
**Pros:**
- Excellent for images/videos with transformations
- Simple API

**Cons:**
- Optimized for media transformations, not document storage
- More expensive for document storage
- Overkill for PDFs

**Cost:** Free tier: 25GB storage, then $0.05-0.10/GB/month

### 1.4 Rationale

**Why S3:**
1. **Production-ready**: Used by millions of applications worldwide
2. **Direct upload pattern**: Clients upload directly to S3 using presigned URLs, reducing server bandwidth and improving scalability
3. **Cost-effective**: Pay only for what you use, no upfront costs
4. **Flexibility**: Can add CloudFront CDN, lifecycle policies, versioning later
5. **Security**: IAM policies provide fine-grained access control
6. **Future-proof**: Easy to migrate to other S3-compatible services if needed

**Why not Supabase:**
- While simpler initially, creates vendor dependency
- If we're not using Supabase for database, adds unnecessary complexity
- S3 gives us more control and flexibility

**Why not Cloudinary:**
- Optimized for media transformations, not document storage
- More expensive for our use case
- We don't need image/video transformations

### 1.5 Architecture Flow

```
┌─────────────┐
│   Client    │
│  (Frontend) │
└──────┬──────┘
       │ 1. POST /api/upload/request-presigned-url
       │    { "filename": "cv.pdf", "content_type": "application/pdf" }
       ▼
┌─────────────────┐
│  FastAPI Server │
└──────┬──────────┘
       │ 2. Generate presigned URL (expires in 5 min)
       │    Returns: { "upload_url": "https://s3...", "file_key": "..." }
       ▼
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 3. PUT file directly to S3 using presigned URL
       ▼
┌─────────────┐
│  AWS S3     │
│  Bucket     │
└─────────────┘
       │
       │ 4. POST /workflow/profiling
       │    { "name": "...", "email": "...", "cv_urls": ["https://..."] }
       ▼
┌─────────────────┐
│ CVProcessingNode│
└──────┬──────────┘
       │ 5. Download PDF from S3 URL
       │ 6. Parse with PDFParser (handles Chinese)
       └───► Continue workflow
```

### 1.6 Implementation Plan

**Phase 1: S3 Setup**
1. Create AWS S3 bucket (e.g., `job-agent-cvs-prod`)
2. Configure CORS for direct client uploads
3. Set up IAM user/role with minimal permissions (PutObject, GetObject)
4. Add environment variables:
   ```bash
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_S3_BUCKET_NAME=job-agent-cvs-prod
   AWS_REGION=us-east-1
   ```

**Phase 2: API Endpoints**
1. `POST /api/upload/presigned-url` - Generate presigned URL for upload (optional; client may use any storage)
2. `POST /workflow/profiling` - Accepts only `cv_urls` (list of CV/PDF URLs). No `pdf_paths` or `data_dir`.

**Phase 3: CV Processing Node**
1. Profiling context has `cv_urls: List[str]` (required). No `pdf_paths` or `data_dir`.
2. `CVProcessingNode` downloads each URL (e.g. via `requests`), writes to a temp file, parses with `PDFParser`, then deletes the temp file. Supports multiple URLs.

**Phase 4: PDF Parser Compatibility**
- Verify `PDFParser` handles Chinese characters correctly
- Test with various PDF encodings
- Consider adding explicit encoding detection if needed

### 1.7 Dependencies

```toml
# Add to pyproject.toml
dependencies = [
    "boto3>=1.34.0",  # AWS SDK for Python
    "botocore>=1.34.0",  # Low-level AWS API
]
```

### 1.8 Security Considerations

1. **Presigned URLs**: Expire after 5 minutes to prevent abuse
2. **File validation**: Validate file type and size before generating presigned URL
3. **Access control**: Use IAM policies to restrict bucket access
4. **Virus scanning**: Consider adding ClamAV or AWS GuardDuty for production
5. **Encryption**: Enable S3 bucket encryption at rest (SSE-S3 or SSE-KMS)

### 1.9 Document Upload Guide

The profiling pipeline accepts **only** a list of CV/PDF URLs (`cv_urls`). There is no support for local paths (`pdf_paths` or `data_dir`).

- **Client responsibility**: Upload PDFs to your chosen storage (e.g. S3 via presigned URL, Cloudinary, or any host that returns a public or signed URL). Send those URLs in the request.
- **API contract**: `POST /workflow/profiling` expects `name`, `email`, and `cv_urls` (list of strings, each an `http://` or `https://` URL). Optional: `basic_info`.
- **Backend behavior**: The server downloads each URL (with timeout and size limit), parses the PDFs with the existing PDFParser, and runs the rest of the workflow. Source URLs are stored in `UserProfile.source_pdfs` for reference.

---

## 2. Job Title Suggestion Feature

### 2.1 Context

Users currently must manually input job titles for the job search workflow. We want to:
- Automatically suggest relevant job titles based on user profile
- Enable users to discover opportunities they might not have considered
- Provide two entry points: manual title input OR AI-suggested titles

### 2.2 Decision

**Extend the profiling workflow to generate a list of suggested job titles using the same LLM agent that generates the profile.**

### 2.3 Architecture

**Update ProfilingOutput Model:**
```python
class ProfilingOutput(BaseModel):
    name: str
    email: str
    profile: str
    references: Optional[dict] = None
    suggested_job_titles: List[str] = Field(
        default_factory=list,
        description="List of 5-10 relevant job titles based on the user's profile, "
                   "skills, experience, and background. Titles should be specific "
                   "and industry-standard (e.g., 'Full-Stack Developer', 'Data Scientist', "
                   "'Registered Chinese Medical Practitioner')."
    )
```

**Update ProfilingWorkflowContext:**
```python
class ProfilingWorkflowContext(BaseContext):
    # ... existing fields ...
    suggested_job_titles: List[str] = Field(default_factory=list)
```

**Update UserProfile Model:**
Add column to store suggested titles:
```python
suggested_job_titles = Column(
    JSON,
    nullable=True,
    doc="List of AI-suggested job titles for this profile"
)
```

### 2.4 Rationale

1. **Single LLM call**: More efficient than separate agent calls
2. **Context-aware**: LLM has full profile context when generating titles
3. **Consistent quality**: Same model ensures consistency between profile and suggestions
4. **Cost-effective**: One API call instead of two
5. **Simple implementation**: Just extend existing Pydantic model and prompt

### 2.5 Prompt Engineering

Update the prompt in `CVProcessingNode` to explicitly request job titles:

```
...existing prompt...

Additionally, analyze the user's profile and suggest 5-10 relevant job titles 
that match their skills, experience, and background. Consider:
- Their technical skills and technologies
- Their work experience and roles
- Their education and certifications
- Industry standards and common job titles

Return job titles as a JSON array in the suggested_job_titles field.
```

### 2.6 Consequences

**Positive:**
- Users discover relevant opportunities automatically
- Reduces friction in job search workflow entry
- Enables multi-run job search (see Section 3)

**Considerations:**
- Need to validate suggested titles before using in job search
- May need to filter out irrelevant or overly generic titles
- Should allow users to edit/remove suggestions

---

## 3. Multi-Run Job Search Architecture

### 3.1 Context

After profiling generates suggested job titles, we want to automatically run job search workflows for each suggested title, rather than requiring manual selection. This enables:
- Comprehensive job discovery across multiple relevant roles
- Better user experience (automatic vs manual)
- Parallel processing of multiple job searches

### 3.2 Decision

**Implement automatic multi-run job search that creates separate workflow executions for each suggested job title, with proper tracking and status management.**

### 3.3 Architecture Design

```
ProfilingWorkflow completes
    │
    ├─► Returns: { profile_id, suggested_job_titles: ["Title1", "Title2", ...] }
    │
    ▼
POST /workflow/job-search/batch
    │
    ├─► For each title in suggested_job_titles:
    │   ├─► Create Run
    │   ├─► Create WorkflowExecution (status: pending)
    │   ├─► Enqueue JobSearchWorkflow task
    │   └─► Return run_id
    │
    └─► Return: {
        "profile_id": "...",
        "job_searches": [
            {"title": "Title1", "run_id": "...", "status": "pending"},
            {"title": "Title2", "run_id": "...", "status": "pending"},
            ...
        ]
    }
```

### 3.4 Implementation Approach

**Option A: Sequential Execution (Simpler)**
- Run job searches one after another
- Simpler error handling
- Slower overall completion

**Option B: Parallel Execution (Selected)**
- Run multiple job searches concurrently
- Faster overall completion
- Better resource utilization
- Requires proper async/threading management

**Decision: Option B (Parallel)** - Better user experience and resource utilization.

### 3.5 New API Endpoint

**`POST /workflow/job-search/batch`**

Request:
```json
{
  "profile_id": "uuid-of-profile",
  "job_titles": ["Software Engineer", "Full-Stack Developer", "Data Scientist"],
  "location": "Hong Kong",
  "num_results": 10,
  "max_screening": 5
}
```

Response (202 Accepted):
```json
{
  "profile_id": "uuid-of-profile",
  "batch_id": "uuid-of-batch",
  "job_searches": [
    {
      "title": "Software Engineer",
      "run_id": "uuid-1",
      "execution_id": "uuid-1-exec",
      "status": "pending",
      "status_url": "/workflow/status/{run_id}"
    },
    {
      "title": "Full-Stack Developer",
      "run_id": "uuid-2",
      "execution_id": "uuid-2-exec",
      "status": "pending",
      "status_url": "/workflow/status/{run_id}"
    }
  ]
}
```

### 3.6 Database Schema Updates

**New Table: `JobSearchBatch`**
```python
class JobSearchBatch(Base):
    """Tracks a batch of job searches for a profile."""
    
    id = Column(UUID, primary_key=True)
    profile_id = Column(UUID, ForeignKey("user_profiles.id"))
    created_at = Column(DateTime)
    completed_count = Column(Integer, default=0)
    total_count = Column(Integer)
    status = Column(String)  # pending, processing, completed, partial_failure
```

**Update `WorkflowExecution`:**
- Add `batch_id` (optional, nullable) to link executions to batches
- Add `job_title` field to track which title this execution is for

### 3.7 Rationale

1. **User Experience**: Users get comprehensive results without manual selection
2. **Scalability**: Can process multiple searches in parallel
3. **Tracking**: Each search has its own `run_id` for status polling
4. **Flexibility**: Users can still use single-title search if preferred
5. **Resource Management**: Can limit concurrent searches if needed

### 3.8 Implementation Considerations

1. **Rate Limiting**: Limit concurrent job searches per user/profile
2. **Error Handling**: If one search fails, others continue
3. **Status Aggregation**: Provide batch-level status endpoint
4. **Cost Management**: Monitor API costs (SerpAPI, LLM calls) per batch

---

## 4. Asynchronous API Pattern

### 4.1 Context

Current API endpoints block until workflow completion, which can take minutes. This causes:
- HTTP timeouts
- Poor user experience
- Inability to track progress
- Resource waste (keeping connections open)

### 4.2 Decision

**Implement asynchronous API pattern using HTTP 202 Accepted with process IDs and status polling endpoints. Use Celery for background task execution.**

### 4.3 Architecture Pattern

**Standard Async Request-Response Pattern:**

```
Client                    FastAPI Server              Celery Worker
  │                            │                            │
  ├─POST /workflow/profiling─►│                            │
  │                            │                            │
  │                            ├─► Validate input          │
  │                            ├─► Create Run               │
  │                            ├─► Create WorkflowExecution │
  │                            ├─► Enqueue Celery task      │
  │                            │                            │
  │◄──202 Accepted─────────────┤                            │
  │   {run_id, status_url}     │                            │
  │                            │                            │
  │                            │                            ├─► Execute workflow
  │                            │                            │   (updates DB)
  │                            │                            │
  │──GET /workflow/status/{id}─►│                            │
  │                            ├─► Query WorkflowExecution │
  │◄──200 OK───────────────────┤                            │
  │   {status, current_node}   │                            │
  │                            │                            │
  │   (poll until completed)   │                            │
```

### 4.4 Options Considered

#### Option A: Celery + Redis (Selected)
**Pros:**
- Industry standard for Python async tasks
- Robust error handling and retries
- Task prioritization and queues
- Monitoring tools (Flower)
- Scales horizontally
- Already documented in `docs/implementation.md`

**Cons:**
- Requires Redis setup
- Additional infrastructure complexity

#### Option B: FastAPI BackgroundTasks
**Pros:**
- Built into FastAPI
- No additional infrastructure
- Simple for small scale

**Cons:**
- Runs in same process (blocks on long tasks)
- No retry mechanism
- No task prioritization
- Doesn't scale horizontally
- Process crash loses tasks

#### Option C: WebSockets
**Pros:**
- Real-time updates (no polling)
- Better UX for progress tracking

**Cons:**
- More complex client implementation
- Connection management overhead
- Still need background task system
- Can combine with polling (hybrid approach)

**Decision: Celery + Redis** - Production-ready, scalable, already planned.

### 4.5 API Endpoint Design

#### 4.5.1 Profiling Workflow (Async)

**`POST /workflow/profiling`**

Request:
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "basic_info": "...",
  "cv_urls": ["https://s3.amazonaws.com/...", "https://..."]
}
```
Profiling accepts only `cv_urls` (list of URLs); no `pdf_paths` or `data_dir`.

Response: **202 Accepted** (instead of 200)
```json
{
  "run_id": "uuid-of-run",
  "execution_id": "uuid-of-execution",
  "status": "pending",
  "status_url": "/workflow/status/{run_id}",
  "estimated_completion_time": "2-5 minutes"
}
```

#### 4.5.2 Status Endpoint

**`GET /workflow/status/{run_id}`**

Response: **200 OK**
```json
{
  "run_id": "uuid-of-run",
  "execution_id": "uuid-of-execution",
  "workflow_type": "profiling",
  "status": "processing",  // pending, processing, completed, failed
  "current_node": "CVProcessingNode",
  "progress_percent": 50,
  "started_at": "2026-01-28T10:00:00Z",
  "completed_at": null,
  "has_errors": false,
  "errors": [],
  "result": {  // Only present when status == "completed"
    "profile_id": "uuid-of-profile",
    "suggested_job_titles": ["...", "..."],
    "name": "...",
    "email": "..."
  }
}
```

#### 4.5.3 Job Search Workflow (Async)

**`POST /workflow/job-search`**

Request:
```json
{
  "profile_id": "uuid-of-profile",
  "query": "Software Engineer",
  "location": "Hong Kong",
  "num_results": 10,
  "max_screening": 5
}
```

Response: **202 Accepted**
```json
{
  "run_id": "uuid-of-run",
  "execution_id": "uuid-of-execution",
  "status": "pending",
  "status_url": "/workflow/status/{run_id}",
  "estimated_completion_time": "5-10 minutes"
}
```

### 4.6 Implementation Plan

**Phase 1: Celery Setup**
1. Install Celery + Redis dependencies
2. Create `src/celery_app.py` with Celery configuration
3. Set up Redis (Docker or managed service)
4. Create task modules:
   - `src/tasks/profiling_task.py`
   - `src/tasks/job_search_task.py`

**Phase 2: Task Implementation**
1. Convert workflow execution to Celery tasks
2. Tasks should:
   - Load context from request
   - Execute workflow
   - Update WorkflowExecution status in DB
   - Handle errors and update status

**Phase 3: API Refactoring**
1. Update `/workflow/profiling` endpoint:
   - Validate input
   - Create Run + WorkflowExecution (status: pending)
   - Enqueue Celery task
   - Return 202 with run_id
2. Create `/workflow/status/{run_id}` endpoint:
   - Query WorkflowExecution from DB
   - Return current status and progress
3. Update `/workflow/job-search` similarly

**Phase 4: Error Handling**
1. Task retry logic (max 3 retries)
2. Error logging and notification
3. Graceful degradation

**Phase 5: Monitoring**
1. Set up Flower for Celery monitoring
2. Add logging for task execution
3. Track task duration and success rates

### 4.7 Rationale

1. **Scalability**: Celery workers can scale independently
2. **Reliability**: Task retries and error handling
3. **Monitoring**: Flower provides task visibility
4. **Industry Standard**: Widely used pattern
5. **Future-proof**: Can add more workflows easily

### 4.8 Dependencies

```toml
# Add to pyproject.toml
dependencies = [
    "celery>=5.3.0",
    "redis>=5.0.0",
    "flower>=2.0.0",  # For monitoring (optional)
]
```

### 4.9 Alternative: Hybrid Approach (Future)

For better UX, can add WebSocket support later:
- Use polling as primary mechanism (simpler)
- Add WebSocket for real-time progress updates (optional enhancement)
- Clients can choose: polling (simpler) or WebSocket (better UX)

---

## 5. Implementation Priority & Timeline

### Phase 1: Foundation (Week 1-2)
1. ✅ S3 setup and presigned URL endpoint
2. ✅ Update CVProcessingNode to handle S3 URLs
3. ✅ Add job title suggestion to ProfilingOutput

### Phase 2: Async API (Week 2-3)
1. ✅ Celery + Redis setup
2. ✅ Convert profiling workflow to async
3. ✅ Add status endpoint
4. ✅ Convert job search workflow to async

### Phase 3: Multi-Run (Week 3-4)
1. ✅ Implement batch job search endpoint
2. ✅ Add JobSearchBatch model
3. ✅ Parallel execution logic
4. ✅ Batch status aggregation

### Phase 4: Testing & Polish (Week 4)
1. ✅ Integration tests
2. ✅ Error handling improvements
3. ✅ Documentation
4. ✅ Performance optimization

---

## 6. Key Architectural Principles

1. **Separation of Concerns**: API layer, workflow layer, and storage layer are decoupled
2. **Idempotency**: Workflow executions can be safely retried
3. **Observability**: All workflows tracked in database with status
4. **Scalability**: Horizontal scaling via Celery workers
5. **User Experience**: Fast API responses (202) with progress tracking
6. **Cost Efficiency**: Pay-as-you-go S3, efficient LLM usage
7. **Security**: Presigned URLs expire, IAM policies restrict access
8. **Flexibility**: Support both single and batch job searches

---

## 7. Open Questions & Future Considerations

1. **Rate Limiting**: How many concurrent job searches per user?
2. **Cost Management**: Monitor and alert on high API costs
3. **WebSocket Enhancement**: Add real-time updates later?
4. **PDF Parsing**: Evaluate Docling vs current PDFParser for better Chinese support
5. **Caching**: Cache suggested job titles to reduce LLM calls?
6. **Analytics**: Track which suggested titles lead to successful applications

---

## 8. References

- [AWS S3 Presigned URLs Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Architecture Decision Records (ADR) Format](https://adr.github.io/)

---

**Document Status**: Ready for Implementation  
**Next Review**: After Phase 1 completion
