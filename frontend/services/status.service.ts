/**
 * Status service for workflow run status.
 * 
 * Provides functions to construct SSE stream URLs and optionally fetch
 * run status via GET fallback (when backend implements it).
 */

import type { RunStatusResponse } from "@/types/workflow";

/**
 * Get the SSE stream URL for a workflow run.
 * 
 * @param runId - UUID of the workflow run
 * @returns Full URL for the SSE status stream endpoint
 */
export function getRunStatusStreamUrl(runId: string): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  // Remove trailing slash if present
  const baseUrl = apiUrl.replace(/\/$/, "");
  return `${baseUrl}/workflow/status/${runId}/stream`;
}

/**
 * Fetch run status via GET request (fallback when SSE is unavailable).
 * 
 * Note: Backend doesn't currently implement GET /workflow/status/{run_id}.
 * This function is a placeholder for future implementation.
 * 
 * @param runId - UUID of the workflow run
 * @returns Promise resolving to run status response
 * @throws Error indicating this endpoint is not yet implemented
 */
export async function fetchRunStatus(
  runId: string
): Promise<RunStatusResponse> {
  // TODO: Implement when backend adds GET /workflow/status/{run_id} endpoint
  throw new Error(
    "GET /workflow/status/{run_id} endpoint not yet implemented. Use SSE stream instead."
  );
}
