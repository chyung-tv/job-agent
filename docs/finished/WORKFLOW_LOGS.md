# Understanding workflow logs

## Why you see errors but the workflow still succeeds

Celery runs multiple workers (e.g. `ForkPoolWorker-1`, `ForkPoolWorker-7`, `ForkPoolWorker-8`). Different tasks or retries can run on different workers, and several workflow runs can be in flight at once. So logs from the same time window can mix:

- **One run** that fails (e.g. missing `job_search_id`, or "Event loop is closed" on a single job match).
- **Another run** that completes (e.g. "FABRICATING COVER LETTERS FOR 2 MATCHED JOBS" and data in the DB).

That’s why you can see "Context validation failed", "No jobs to persist", or "Event loop is closed" and still have a successful outcome and correct data in the database: the failing lines belong to other runs or to non-fatal steps (e.g. one job failing to match while the rest succeed).

## Common log messages

| Log | Meaning |
|-----|--------|
| **Failed to match job … Event loop is closed** | One job in the matching step hit an async/event-loop issue (e.g. client cleanup). That job is skipped; other jobs in the same run can still be matched. |
| **No jobs to persist** | This run’s discovery step had no jobs to save, or the matching step had no matches. Often from a different run or a step that didn’t have jobs in context. |
| **Context validation failed** / **Jobs list or job_search_id is required** | This run’s matching step was called without `jobs` or `job_search_id` (e.g. wrong payload or continuation without context). That run fails validation; others can still succeed. |
| **No matched results or job_search_id to persist** | Matching ran but produced no matches, or `job_search_id` was missing, so nothing was written to the DB for that run. |
| **FABRICATING COVER LETTERS FOR N MATCHED JOBS** | A run reached the fabrication step with N matched jobs and started generating cover letters. This indicates a successful path. |

## What “normal” looks like

- You may see warnings/errors from **other** runs or from **single-job** failures inside an otherwise successful run.
- A **successful** end-to-end run will show: discovery → matching (with some matches) → research → fabrication ("FABRICATING COVER LETTERS…") and the expected rows in the database.
- So it’s normal for the log to contain both failure lines and success lines; the important part is that at least one run completes and the DB reflects it.
