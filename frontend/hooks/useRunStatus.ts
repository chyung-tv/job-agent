/**
 * React hook for streaming workflow run status via SSE (Server-Sent Events).
 * 
 * Uses the browser's native EventSource API to connect to the SSE stream
 * and parse status updates in real-time.
 */

import { useEffect, useState, useRef, startTransition } from "react";
import { z } from "zod";
import { getRunStatusStreamUrl } from "@/services/status.service";
import {
  runStatusEventSchema,
  type RunStatusEvent,
  RunStatus,
} from "@/types/workflow";

// Extract RunStatus type from Zod enum
type RunStatusType = z.infer<typeof RunStatus>;

export interface UseRunStatusReturn {
  /** Current workflow status */
  status: RunStatusType | null;
  /** Current workflow node name */
  node: string | null;
  /** Optional status message */
  message: string | null;
  /** ISO timestamp when workflow completed/failed */
  completed_at: string | null;
  /** Error message if status is failed */
  error_message: string | null;
  /** Whether the SSE connection is currently active */
  isConnected: boolean;
  /** Connection error if any */
  connectionError: Error | null;
}

/**
 * Hook to stream workflow run status via SSE.
 * 
 * @param runId - UUID of the workflow run to monitor
 * @param enabled - Whether to enable the SSE connection (default: true)
 * @returns Status state and connection info
 * 
 * @example
 * ```tsx
 * const { status, node, message, isConnected } = useRunStatus(runId);
 * 
 * if (status === "completed") {
 *   // Handle completion
 * }
 * ```
 */
export function useRunStatus(
  runId: string,
  enabled: boolean = true
): UseRunStatusReturn {
  const [status, setStatus] = useState<RunStatusType | null>(null);
  const [node, setNode] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [completed_at, setCompletedAt] = useState<string | null>(null);
  const [error_message, setErrorMessage] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<Error | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const previousRunIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !runId) {
      return;
    }

    // Track if runId changed
    const runIdChanged = previousRunIdRef.current !== null && previousRunIdRef.current !== runId;
    previousRunIdRef.current = runId;

    const streamUrl = getRunStatusStreamUrl(runId);

    // Create EventSource connection
    // Note: EventSource doesn't support custom headers, so API key auth
    // must be handled via query param or a Next.js API proxy route
    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      // Reset state when runId changes (using startTransition to avoid cascading renders)
      if (runIdChanged) {
        startTransition(() => {
          setStatus(null);
          setNode(null);
          setMessage(null);
          setCompletedAt(null);
          setErrorMessage(null);
          setConnectionError(null);
        });
      }
      setIsConnected(true);
      setConnectionError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        // Parse JSON from SSE data line
        const data = JSON.parse(event.data);

        // Validate with Zod schema
        const parsed = runStatusEventSchema.parse(data);
        const statusEvent: RunStatusEvent = parsed;

        // Update state
        setStatus(statusEvent.status);
        if (statusEvent.node !== undefined) {
          setNode(statusEvent.node);
        }
        if (statusEvent.message !== undefined) {
          setMessage(statusEvent.message);
        }
        if (statusEvent.completed_at !== undefined) {
          setCompletedAt(statusEvent.completed_at);
        }
        if (statusEvent.error_message !== undefined) {
          setErrorMessage(statusEvent.error_message);
        }

        // Close connection when workflow completes or fails
        if (
          statusEvent.status === "completed" ||
          statusEvent.status === "failed"
        ) {
          eventSource.close();
          setIsConnected(false);
        }
      } catch (error) {
        console.error("Failed to parse SSE event:", error, event.data);
        setConnectionError(
          error instanceof Error
            ? error
            : new Error("Failed to parse SSE event")
        );
      }
    };

    eventSource.onerror = (error) => {
      console.error("EventSource error:", error);
      setConnectionError(
        new Error("SSE connection error. Check network and API availability.")
      );
      setIsConnected(false);
      // EventSource will automatically attempt to reconnect
      // Close manually if we want to stop retrying
    };

    // Cleanup on unmount or when runId/enabled changes
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
      }
    };
  }, [runId, enabled]);

  return {
    status,
    node,
    message,
    completed_at,
    error_message,
    isConnected,
    connectionError,
  };
}
