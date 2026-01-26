# Database Setup Guide

This guide explains how to set up and use PostgreSQL with SQLAlchemy in the job-agent project.

## Quick Start

### 1. Install Dependencies

```bash
uv sync
# or
pip install -e .
```

This will install SQLAlchemy and psycopg3.

### 2. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

Verify it's running:
```bash
docker-compose ps
```

### 3. Create Database Tables

```bash
python create_tables.py
```

This will create three tables:
- `job_searches` - Workflow runs
- `job_postings` - Individual job results
- `matched_jobs` - AI-screened matches

### 4. Connect with TablePlus

- **Host**: `localhost`
- **Port**: `5432`
- **User**: `postgres`
- **Password**: `postgres`
- **Database**: `job_agent`
- **SSL**: Disable

## Project Structure

```
src/database/
├── __init__.py          # Module exports
├── database_utils.py    # Connection string utilities
├── session.py           # SQLAlchemy session management
├── repository.py        # Generic repository pattern
└── models.py            # Database models (JobSearch, JobPosting, MatchedJob)
```

## Database Models

### JobSearch
Stores workflow run metadata:
- Search parameters (query, location, etc.)
- Summary statistics (total jobs, screened, matches)

### JobPosting
Stores individual job results from SerpAPI:
- Job details (title, company, location, description)
- JSON fields for complex data (extensions, highlights, apply options)

### MatchedJob
Stores AI screening results:
- Match status and reasoning
- Application links
- Linked to both JobSearch and JobPosting

## Usage Examples

### Basic CRUD Operations

```python
from src.database import db_session, GenericRepository, JobSearch

# Get session
session = next(db_session())
repo = GenericRepository(session, JobSearch)

# Create
new_search = JobSearch(query="software engineer", location="Hong Kong")
created = repo.create(new_search)

# Read
search = repo.get(str(created.id))
all_searches = repo.get_all()

# Update
search.matches_found = 5
repo.update(search)

# Delete
repo.delete(str(search.id))

session.close()
```

### Query with Filters

```python
# Filter by location
hk_searches = repo.filter_by(location="Hong Kong")

# Find one
search = repo.find_one(query="software engineer", location="Hong Kong")

# Get latest
latest = repo.get_latest(5)
```

### Using Relationships

```python
# Get job search with related postings
search = repo.get(search_id)
print(f"Found {len(search.job_postings)} job postings")
print(f"Matched {len(search.matched_jobs)} jobs")

# Access related data
for posting in search.job_postings:
    print(f"{posting.title} at {posting.company_name}")
```

## Important Notes

### Connection String Format

**CRITICAL**: The project uses `psycopg3`, so the connection string must use:
```
postgresql+psycopg://user:pass@host:port/db
```

NOT `postgresql://` (which defaults to psycopg2).

This is already configured in `.env` and `database_utils.py`.

### Port Conflicts

If port 5432 is already in use:

1. Check what's using it:
   ```bash
   lsof -i :5432
   ```

2. Stop local PostgreSQL:
   ```bash
   brew services stop postgresql@15
   ```

3. Or change Docker port in `docker-compose.yml`:
   ```yaml
   ports:
     - "5433:5432"  # Use 5433 instead
   ```

### Session Management

Always close sessions after use:
```python
session = next(db_session())
try:
    # Use session
    pass
finally:
    session.close()
```

Or use the context manager pattern (the `db_session()` generator handles commits/rollbacks automatically).

## Troubleshooting

### "ModuleNotFoundError: No module named 'psycopg2'"

**Solution**: Make sure you're using `postgresql+psycopg://` in the connection string (already configured).

### "port 5432 already in use"

**Solution**: Stop local PostgreSQL or change Docker port.

### Tables not appearing in TablePlus

**Solution**: 
1. Refresh TablePlus (right-click database → Refresh)
2. Verify tables exist: `docker exec -it job-agent-postgres psql -U postgres -d job_agent -c "\dt"`

### Connection refused

**Solution**:
1. Wait 10-15 seconds after starting Docker
2. Check container: `docker ps`
3. Check logs: `docker logs job-agent-postgres`

## Next Steps

1. Integrate database operations into `workflow.py`
2. Store job search results automatically
3. Add database queries to retrieve historical searches
4. Implement data persistence for user profiles

See `example_database_usage.py` for complete examples.
