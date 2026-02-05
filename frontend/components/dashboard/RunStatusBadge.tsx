"use client";

import { useRouter } from "next/navigation";
import { useRunStatus } from "@/hooks/useRunStatus";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface RunStatusBadgeProps {
  runId: string;
  initialStatus: string;
}

const statusConfig: Record<
  string,
  { label: string; className: string; showSpinner?: boolean }
> = {
  pending: {
    label: "Pending",
    className: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    showSpinner: true,
  },
  processing: {
    label: "Processing",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    showSpinner: true,
  },
  completed: {
    label: "Completed",
    className: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  },
};

export function RunStatusBadge({ runId, initialStatus }: RunStatusBadgeProps) {
  const router = useRouter();
  
  // Only use SSE for in-progress runs
  const shouldStream = initialStatus === "pending" || initialStatus === "processing";
  const { status: liveStatus, node } = useRunStatus(
    shouldStream ? runId : "",
    {
      onComplete: () => {
        // Refresh the page data when workflow completes to update matched jobs count
        router.refresh();
      },
    }
  );

  // Use live status if available and streaming, otherwise use initial
  const currentStatus = shouldStream && liveStatus ? liveStatus : initialStatus;
  const config = statusConfig[currentStatus] || statusConfig.pending;

  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
          config.className
        )}
      >
        {config.showSpinner && (
          <Loader2 className="h-3 w-3 animate-spin" />
        )}
        {config.label}
      </span>
      {shouldStream && node && (
        <span className="text-xs text-muted-foreground">
          {node.replace(/_/g, " ")}
        </span>
      )}
    </div>
  );
}
