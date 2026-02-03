/**
 * Workflow service for URL construction and parameter formatting.
 * 
 * This is a helper service that can be used by Server Actions or client components
 * (without API_KEY) for constructing API URLs. The actual API calls with authentication
 * must be made via Server Actions in actions/workflow.ts.
 */

/**
 * Get the API base URL from environment variables.
 */
function getApiUrl(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return apiUrl.replace(/\/$/, ""); // Remove trailing slash
}

/**
 * Get the URL for the profiling workflow endpoint.
 * 
 * @returns Full URL for POST /workflow/profiling
 */
export function getProfilingUrl(): string {
  return `${getApiUrl()}/workflow/profiling`;
}

/**
 * Get the URL for the job search workflow endpoint.
 * 
 * @returns Full URL for POST /workflow/job-search
 */
export function getJobSearchUrl(): string {
  return `${getApiUrl()}/workflow/job-search`;
}

/**
 * Get the URL for the job search from profile endpoint.
 * 
 * @returns Full URL for POST /workflow/job-search/from-profile
 */
export function getJobSearchFromProfileUrl(): string {
  return `${getApiUrl()}/workflow/job-search/from-profile`;
}

/**
 * Get the URL for the status stream endpoint.
 * 
 * @param runId - UUID of the workflow run
 * @returns Full URL for GET /workflow/status/{runId}/stream
 */
export function getStatusStreamUrl(runId: string): string {
  return `${getApiUrl()}/workflow/status/${runId}/stream`;
}
