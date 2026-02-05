"use client";

import { useRouter } from "next/navigation";
import { useRunStatus } from "@/hooks/useRunStatus";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Loader2, CheckCircle2, XCircle, Clock, Zap } from "lucide-react";

interface RunStatusBadgeProps {
  runId: string;
  initialStatus: string;
}

const statusConfig: Record<
  string,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline";
    className: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  pending: {
    label: "Pending",
    variant: "outline",
    className: "border-yellow-500/30 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400",
    icon: Clock,
  },
  processing: {
    label: "Processing",
    variant: "outline",
    className: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400",
    icon: Zap,
  },
  completed: {
    label: "Completed",
    variant: "outline",
    className: "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400",
    icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    className: "",
    icon: XCircle,
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
  const isActive = currentStatus === "pending" || currentStatus === "processing";
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <Badge
        variant={config.variant}
        className={cn(
          "gap-1.5 font-medium",
          config.className
        )}
      >
        {isActive ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <Icon className="h-3 w-3" />
        )}
        {config.label}
      </Badge>
      {shouldStream && node && (
        <span className="text-xs text-muted-foreground">
          {node.replace(/_/g, " ")}
        </span>
      )}
    </div>
  );
}
