"use server";

/**
 * Server Actions for triggering workflow executions.
 * 
 * These actions run on the server and use API_KEY from environment variables
 * to authenticate with the FastAPI backend. API_KEY is never exposed to the client.
 */

import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { headers } from "next/headers";
import {
  profilingWorkflowRequestSchema,
  profilingWorkflowResponseSchema,
  jobSearchWorkflowRequestSchema,
  jobSearchWorkflowResponseSchema,
  jobSearchFromProfileRequestSchema,
  jobSearchFromProfileResponseSchema,
  type ProfilingWorkflowRequest,
  type ProfilingWorkflowResponse,
  type JobSearchWorkflowRequest,
  type JobSearchWorkflowResponse,
  type JobSearchFromProfileRequest,
  type JobSearchFromProfileResponse,
} from "@/types/workflow";

/**
 * Get the API base URL from environment variables.
 */
function getApiUrl(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return apiUrl.replace(/\/$/, ""); // Remove trailing slash
}

/**
 * Get the API key from environment variables (server-side only).
 */
function getApiKey(): string {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error(
      "API_KEY is not configured. Please set API_KEY in your environment variables."
    );
  }
  return apiKey;
}

/**
 * Make an authenticated API request to the backend.
 */
async function makeApiRequest<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const apiKey = getApiKey();
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}. ${errorText}`
    );
  }

  return response.json();
}

/**
 * Check if current user has beta access.
 * Throws an error if user doesn't have access.
 * @returns The authenticated user's ID
 */
async function requireBetaAccess(): Promise<string> {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    throw new Error("Authentication required");
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: { hasAccess: true },
  });

  if (!user?.hasAccess) {
    throw new Error(
      "Beta access required. Please email chyung.tv@gmail.com to request access."
    );
  }

  return session.user.id;
}

/**
 * Trigger the profiling workflow.
 * 
 * @param data - Profiling workflow request data
 * @returns Profiling workflow response with run_id and status
 * @throws Error if validation fails or API request fails
 */
export async function triggerProfiling(
  data: ProfilingWorkflowRequest
): Promise<ProfilingWorkflowResponse> {
  // Validate request data
  const validatedData = profilingWorkflowRequestSchema.parse(data);

  const apiUrl = getApiUrl();
  const url = `${apiUrl}/workflow/profiling`;

  const response = await makeApiRequest<ProfilingWorkflowResponse>(url, {
    method: "POST",
    body: JSON.stringify(validatedData),
  });

  // Validate response
  const parsed = profilingWorkflowResponseSchema.parse(response);
  if (validatedData.basic_info) {
    console.log(
      "[triggerProfiling] Second profiling trigger (basic_info present), run_id:",
      parsed.run_id,
      "task_id:",
      parsed.task_id
    );
  }
  return parsed;
}

/**
 * Trigger the job search workflow.
 * 
 * @param data - Job search workflow request data
 * @returns Job search workflow response with run_id and status
 * @throws Error if validation fails, user lacks beta access, or API request fails
 */
export async function triggerJobSearch(
  data: JobSearchWorkflowRequest
): Promise<JobSearchWorkflowResponse> {
  // Check beta access FIRST (server-side enforcement)
  await requireBetaAccess();

  // Validate request data
  const validatedData = jobSearchWorkflowRequestSchema.parse(data);

  const apiUrl = getApiUrl();
  const url = `${apiUrl}/workflow/job-search`;

  const response = await makeApiRequest<JobSearchWorkflowResponse>(url, {
    method: "POST",
    body: JSON.stringify(validatedData),
  });

  // Validate response
  return jobSearchWorkflowResponseSchema.parse(response);
}

/**
 * Trigger job searches from a user's profile.
 * 
 * This endpoint loads the user's profile and triggers job searches
 * for each suggested job title.
 * 
 * @param data - Job search from profile request data
 * @returns Job search from profile response with job titles and counts
 * @throws Error if validation fails, user lacks beta access, or API request fails
 */
export async function triggerJobSearchFromProfile(
  data: JobSearchFromProfileRequest
): Promise<JobSearchFromProfileResponse> {
  // Check beta access FIRST (server-side enforcement)
  await requireBetaAccess();

  // Validate request data
  const validatedData = jobSearchFromProfileRequestSchema.parse(data);

  const apiUrl = getApiUrl();
  const url = `${apiUrl}/workflow/job-search/from-profile`;

  const response = await makeApiRequest<JobSearchFromProfileResponse>(url, {
    method: "POST",
    body: JSON.stringify(validatedData),
  });

  // Validate response
  return jobSearchFromProfileResponseSchema.parse(response);
}
