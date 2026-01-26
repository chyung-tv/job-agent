# Database Fixes and User Profile Implementation

## Issues Fixed

### 1. Job Postings and Matched Jobs Not Being Saved

**Problem**: Only `job_searches` records were being saved, but `job_postings` and `matched_jobs` were not appearing in the database.

**Root Cause**: The session generator (`db_session()`) wasn't being properly consumed, which meant commits weren't happening. The generator pattern requires proper consumption to trigger the commit logic.

**Solution**: 
- Changed from `session = next(db_session())` to properly consume the generator
- Added better error logging to see what's happening
- Added per-item error handling so one failure doesn't stop all saves
- Added success counters to show how many records were saved

**Changes Made**:
- `src/discovery/serpapi_service.py`: Fixed session handling in `_save_jobs_to_db()`
- `src/matcher/matcher.py`: Fixed session handling in `_save_matched_jobs_to_db()`

### 2. User Profile Caching

**New Feature**: Added `UserProfile` model to cache user profiles and avoid calling LLM every time.

**Benefits**:
- Faster workflow execution (no LLM call if profile exists)
- Cost savings (fewer API calls)
- Automatic cache invalidation when PDFs change (using hash)

## User Profile Model

### Database Schema

```python
class UserProfile(Base):
    id: UUID                    # Primary key
    profile_text: Text          # The structured profile text
    source_pdfs: JSON           # List of PDF file paths
    profile_hash: String(64)    # Hash of PDFs (for cache invalidation)
    created_at: DateTime
    updated_at: DateTime
    last_used_at: DateTime      # Track when profile was last used
```

### How It Works

1. **Cache Check**: When `build_user_profile()` is called, it first checks the database for a cached profile with matching PDF hash
2. **Hash Calculation**: Computes SHA256 hash based on:
   - PDF file paths
   - File modification times
   - File sizes
3. **Cache Hit**: If profile exists and hash matches, returns cached profile (no LLM call)
4. **Cache Miss**: If not found or PDFs changed:
   - Extracts text from PDFs
   - Calls LLM to structure the profile
   - Saves to database
5. **Auto-Update**: If profile exists but PDFs changed, updates the existing record

## Usage

### Automatic Caching

The workflow automatically uses cached profiles:

```python
from src.profiling.profile import build_user_profile

# First call - extracts PDFs, calls LLM, saves to DB
profile = build_user_profile()  # use_cache=True by default

# Second call - loads from database (no LLM call!)
profile = build_user_profile()  # Fast! Uses cache
```

### Force Regeneration

To force regeneration (ignore cache):

```python
profile = build_user_profile(use_cache=False)
```

### Manual Profile Management

```python
from src.database import db_session, GenericRepository, UserProfile

session_gen = db_session()
session = next(session_gen)
try:
    profile_repo = GenericRepository(session, UserProfile)
    
    # Get latest profile
    latest = profile_repo.get_latest(1)[0]
    print(f"Profile: {latest.profile_text[:100]}...")
    print(f"Source PDFs: {latest.source_pdfs}")
    print(f"Last used: {latest.last_used_at}")
    
    # Find by hash
    profile = profile_repo.find_one(profile_hash="...")
finally:
    try:
        next(session_gen, None)
    except StopIteration:
        pass
```

## Database Tables

After running `python create_tables.py`, you'll have:

1. **job_searches** - Workflow runs
2. **job_postings** - Individual job results
3. **matched_jobs** - AI-screened matches
4. **user_profiles** - Cached user profiles (NEW)

## Testing

### Verify Database Saves

Run the workflow and check for these log messages:

```
[DATABASE] Created JobSearch: <uuid>
[DATABASE] Saved 10/10 job postings
[DATABASE] Saved 3/3 matched jobs
[DATABASE] Updated JobSearch statistics
[DATABASE] Found cached user profile (ID: <uuid>)
```

### Check Database

```sql
-- Check job searches
SELECT id, query, location, total_jobs_found, matches_found 
FROM job_searches 
ORDER BY created_at DESC LIMIT 5;

-- Check job postings
SELECT COUNT(*) FROM job_postings;
SELECT title, company_name FROM job_postings LIMIT 5;

-- Check matched jobs
SELECT COUNT(*) FROM matched_jobs;
SELECT m.is_match, m.reason, p.title 
FROM matched_jobs m 
JOIN job_postings p ON m.job_posting_id = p.id 
LIMIT 5;

-- Check user profiles
SELECT id, profile_hash, created_at, last_used_at 
FROM user_profiles 
ORDER BY last_used_at DESC;
```

## Migration Steps

1. **Update database schema**:
   ```bash
   python create_tables.py
   ```
   This will create the new `user_profiles` table.

2. **Test the workflow**:
   ```bash
   python test_workflow.py
   ```

3. **Verify data**:
   - Check TablePlus or run SQL queries above
   - First run should create all records
   - Second run should use cached profile (faster)

## Error Handling

All database operations have error handling:
- Errors are logged but don't crash the workflow
- Per-item errors are caught so one failure doesn't stop others
- Database unavailability is handled gracefully

## Performance Improvements

- **First run**: Normal speed (extracts PDFs, calls LLM)
- **Subsequent runs**: Much faster (uses cached profile)
- **After PDF update**: Automatically detects change and regenerates

## Notes

- Profile hash is based on file paths, modification times, and sizes
- Changing PDF content will automatically invalidate cache
- Multiple profiles can exist (one per unique PDF set)
- `last_used_at` tracks when profile was last used in a search
