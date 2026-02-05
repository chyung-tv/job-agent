/**
 * Zod schemas and TypeScript types for workflow API requests/responses and SSE events.
 * 
 * These schemas provide runtime validation for API interactions and type safety
 * through TypeScript type inference using z.infer.
 */

import { z } from "zod";

// ============================================================================
// Status and Node Types
// ============================================================================

/**
 * Workflow run status values.
 */
export const RunStatus = z.enum(["pending", "processing", "completed", "failed"]);

/**
 * Common workflow node names.
 */
export const WorkflowNode = z.enum([
  "UserInputNode",
  "CVProcessingNode",
  "ProfileRetrievalNode",
  "DiscoveryNode",
  "MatchingNode",
  "ResearchNode",
  "FabricationNode",
  "CompletionNode",
  "DeliveryNode",
]);

// ============================================================================
// Profiling Workflow
// ============================================================================

/**
 * Zod schema for profiling workflow request.
 */
export const profilingWorkflowRequestSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email address"),
  location: z.string().min(1, "Location is required"),
  basic_info: z.string().optional(),
  cv_urls: z.array(z.string().url("CV URL must be a valid URL")).min(1, "At least one CV URL is required"),
});

/**
 * TypeScript type for profiling workflow request.
 */
export type ProfilingWorkflowRequest = z.infer<typeof profilingWorkflowRequestSchema>;

/**
 * Zod schema for profiling workflow response.
 */
export const profilingWorkflowResponseSchema = z.object({
  run_id: z.string().uuid("Invalid run ID format"),
  task_id: z.string().min(1, "Task ID is required"),
  status: RunStatus,
  status_url: z.string().min(1, "Status URL is required"), // Relative path, not full URL
  estimated_completion_time: z.string().min(1, "Estimated completion time is required"),
});

/**
 * TypeScript type for profiling workflow response.
 */
export type ProfilingWorkflowResponse = z.infer<typeof profilingWorkflowResponseSchema>;

// ============================================================================
// Job Search Workflow
// ============================================================================

/**
 * Zod schema for job search workflow request.
 */
export const jobSearchWorkflowRequestSchema = z.object({
  query: z.string().min(1, "Query is required"),
  location: z.string().min(1, "Location is required"),
  user_id: z.string().min(1, "User ID is required").optional(),
  num_results: z.number().int().positive().optional(),
  max_screening: z.number().int().positive().optional(),
  google_domain: z.string().optional(),
  hl: z.string().optional(),
  gl: z.string().optional(),
});

/**
 * TypeScript type for job search workflow request.
 */
export type JobSearchWorkflowRequest = z.infer<typeof jobSearchWorkflowRequestSchema>;

/**
 * Zod schema for job search workflow response.
 */
export const jobSearchWorkflowResponseSchema = z.object({
  run_id: z.string().uuid("Invalid run ID format"),
  task_id: z.string().min(1, "Task ID is required"),
  status: RunStatus,
  status_url: z.string().min(1, "Status URL is required"),
  estimated_completion_time: z.string().min(1, "Estimated completion time is required"),
});

/**
 * TypeScript type for job search workflow response.
 */
export type JobSearchWorkflowResponse = z.infer<typeof jobSearchWorkflowResponseSchema>;

// ============================================================================
// Job Search from Profile
// ============================================================================

/**
 * Zod schema for job search from profile request.
 */
export const jobSearchFromProfileRequestSchema = z.object({
  user_id: z.string().min(1, "User ID is required"),
  num_results: z.number().int().positive().optional(),
  max_screening: z.number().int().positive().optional(),
});

/**
 * TypeScript type for job search from profile request.
 */
export type JobSearchFromProfileRequest = z.infer<typeof jobSearchFromProfileRequestSchema>;

/**
 * Zod schema for job search from profile response.
 */
export const jobSearchFromProfileResponseSchema = z.object({
  message: z.string().min(1, "Message is required"),
  user_id: z.string().min(1, "User ID is required"),
  location: z.string().min(1, "Location is required"),
  job_titles_count: z.number().int().nonnegative("Job titles count must be non-negative"),
  job_titles: z.array(z.string().min(1, "Job title cannot be empty")),
});

/**
 * TypeScript type for job search from profile response.
 */
export type JobSearchFromProfileResponse = z.infer<typeof jobSearchFromProfileResponseSchema>;

// ============================================================================
// Status (SSE Event)
// ============================================================================

/**
 * Zod schema for run status event (SSE payload).
 * 
 * Note: Backend doesn't use `step` field, only `node`.
 */
export const runStatusEventSchema = z.object({
  status: RunStatus,
  node: WorkflowNode.optional(),
  message: z.string().optional(),
  completed_at: z.string().datetime({ message: "Invalid ISO datetime format" }).optional(),
  error_message: z.string().optional(),
});

/**
 * TypeScript type for run status event (SSE payload).
 */
export type RunStatusEvent = z.infer<typeof runStatusEventSchema>;

// ============================================================================
// Status (GET Fallback)
// ============================================================================

/**
 * Zod schema for run status response (GET fallback).
 * 
 * Matches the `runs` table structure from Prisma schema.
 */
export const runStatusResponseSchema = z.object({
  run_id: z.string().uuid("Invalid run ID format"),
  task_id: z.string().nullable(),
  status: RunStatus,
  error_message: z.string().nullable(),
  completed_at: z.string().datetime({ message: "Invalid ISO datetime format" }).nullable(),
  user_id: z.string().nullable(),
  job_search_id: z.string().uuid("Invalid job search ID format").nullable(),
  total_matched_jobs: z.number().int().nonnegative().default(0),
  research_completed_count: z.number().int().nonnegative().default(0),
  fabrication_completed_count: z.number().int().nonnegative().default(0),
  research_failed_count: z.number().int().nonnegative().default(0),
  fabrication_failed_count: z.number().int().nonnegative().default(0),
  delivery_triggered: z.boolean().default(false),
  delivery_triggered_at: z.string().datetime({ message: "Invalid ISO datetime format" }).nullable(),
  created_at: z.string().datetime({ message: "Invalid ISO datetime format" }),
  updated_at: z.string().datetime({ message: "Invalid ISO datetime format" }),
});

/**
 * TypeScript type for run status response (GET fallback).
 */
export type RunStatusResponse = z.infer<typeof runStatusResponseSchema>;
