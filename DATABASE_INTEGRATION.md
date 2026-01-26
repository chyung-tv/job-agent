# Database Integration Summary

This document describes how the discovery, matcher, and profiling modules have been refactored to save data to the database.

## Overview

All three modules now support optional database persistence:
- **Discovery**: Saves `JobSearch` and `JobPosting` records
- **Matcher**: Saves `MatchedJob` records
- **Profiling**: No changes needed (produces user profile string used in matching)

## Changes Made

### 1. Discovery Service (`src/discovery/serpapi_service.py`)

**New Features:**
- `search_jobs()` now returns a tuple: `(List[JobResult], Optional[uuid.UUID])`
- Added `save_to_db` parameter (default: `True`)
- Added `job_search_id` parameter for linking to existing searches
- Automatically creates `JobSearch` record when saving
- Saves all `JobPosting` records linked to the `JobSearch`

**Usage:**
```python
jobs, job_search_id = service.search_jobs(
    query="software engineer",
    location="Hong Kong",
    save_to_db=True,  # Optional, defaults to True
)
```

**What Gets Saved:**
- `JobSearch`: Search parameters and metadata
- `JobPosting`: Each job result with full details (title, company, description, JSON fields)

### 2. Matcher (`src/matcher/matcher.py`)

**New Features:**
- `screen_jobs()` now accepts `job_search_id` and `job_posting_map`
- Added `save_to_db` parameter (default: `True`)
- Saves `MatchedJob` records for all matched jobs
- Updates `JobSearch` statistics (jobs_screened, matches_found)

**Usage:**
```python
matched_results = screening_agent.screen_jobs(
    user_profile=user_profile,
    jobs=jobs,
    job_search_id=job_search_id,
    job_posting_map=job_posting_map,
    save_to_db=True,  # Optional, defaults to True
)
```

**What Gets Saved:**
- `MatchedJob`: Match status, reason, application links
- Linked to both `JobSearch` and `JobPosting` via foreign keys
- Updates `JobSearch.jobs_screened` and `JobSearch.matches_found`

### 3. Workflow (`src/workflow.py`)

**New Features:**
- Handles tuple return from `search_jobs()`
- Builds `job_posting_map` to link job IDs to database UUIDs
- Passes database context to matcher
- Updates final statistics in `JobSearch`

**Flow:**
1. Discovery creates `JobSearch` and `JobPosting` records
2. Workflow builds mapping of `job_id` → `JobPosting.uuid`
3. Matcher uses mapping to create `MatchedJob` records
4. Workflow updates final `JobSearch` statistics

## Error Handling

All database operations are wrapped in try-except blocks:
- Database errors are logged as warnings
- Workflow continues even if database save fails
- No breaking changes if database is unavailable

**Example:**
```python
try:
    # Database operation
except Exception as e:
    print(f"[WARNING] Failed to save to database: {e}")
    # Continue execution
```

## Database Schema Relationships

```
JobSearch (1) ──< (many) JobPosting
    │
    └──< (many) MatchedJob ──> (1) JobPosting
```

- One `JobSearch` has many `JobPosting` records
- One `JobSearch` has many `MatchedJob` records
- One `MatchedJob` belongs to one `JobPosting`

## Backward Compatibility

- All new parameters have default values
- Existing code will continue to work
- Database operations are optional (can be disabled with `save_to_db=False`)

## Usage Example

```python
from src.workflow import run

# This will automatically save everything to the database
matched_jobs = run(
    query="software engineer",
    location="Hong Kong",
    num_results=30,
    max_screening=5,
)
```

The workflow will:
1. Create a `JobSearch` record
2. Save all 30 `JobPosting` records
3. Screen 5 jobs and save `MatchedJob` records for matches
4. Update `JobSearch` with final statistics

## Querying Saved Data

```python
from src.database import db_session, GenericRepository, JobSearch

session = next(db_session())
repo = GenericRepository(session, JobSearch)

# Get latest search
latest = repo.get_latest(1)[0]
print(f"Query: {latest.query}")
print(f"Found {latest.total_jobs_found} jobs")
print(f"Matched {latest.matches_found} jobs")

# Access related data
for posting in latest.job_postings[:5]:
    print(f"- {posting.title} at {posting.company_name}")

for match in latest.matched_jobs:
    print(f"✓ {match.job_posting.title}: {match.reason}")

session.close()
```

## Notes

- Profiling module doesn't need database changes - it produces a user profile string that's used in matching
- User profiles are not stored separately (they're part of the matching context)
- If you want to store user profiles, consider adding a `UserProfile` model in the future
