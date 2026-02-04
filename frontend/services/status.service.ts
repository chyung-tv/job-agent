/**
 * Status service for workflow run status.
 * 
 * Provides functions to construct SSE stream URLs and optionally fetch
 * run status via GET fallback (when backend implements it).
 */

import { runStatusResponseSchema, type RunStatusResponse } from "@/types/workflow";

/**
 * Get the SSE stream URL for a workflow run.
 * Uses same-origin Next.js proxy so the browser does not need to send the API key
 * and CORS is avoided.
 *
 * @param runId - UUID of the workflow run
 * @returns Same-origin path to the proxy (e.g. /api/workflow/status/{runId}/stream)
 */
export function getRunStatusStreamUrl(runId: string): string {
  return `/api/workflow/status/${runId}/stream`;
}

/**
 * Fetch run status via GET request (fallback when SSE is unavailable).
 * 
 * Note: This endpoint requires API_KEY authentication. For client-side usage,
 * this should be called through a Next.js API route proxy or Server Action
 * that adds the API_KEY header.
 * 
 * @param runId - UUID of the workflow run
 * @returns Promise resolving to run status response
 * @throws Error if request fails or run not found
 */
export async function fetchRunStatus(
  runId: string
): Promise<RunStatusResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const baseUrl = apiUrl.replace(/\/$/, "");
  const url = `${baseUrl}/workflow/status/${runId}`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Run with id ${runId} not found`);
    }
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(
      `Failed to fetch run status: ${response.status} ${response.statusText}. ${errorText}`
    );
  }

  const data = await response.json();
  
  // Validate response with Zod schema
  return runStatusResponseSchema.parse(data);
}
