"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useRunStatus } from "@/hooks/useRunStatus";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo } from "react";
import { CheckCircle2, Circle, Loader2, XCircle, FileText, User, Upload, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface Step {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  nodes: string[];
}

const STEPS: Step[] = [
  {
    id: "submitted",
    label: "Submitted",
    icon: Upload,
    nodes: ["pending"],
  },
  {
    id: "parsing",
    label: "Parsing CV",
    icon: FileText,
    nodes: ["UserInputNode", "CVProcessingNode"],
  },
  {
    id: "building",
    label: "Building Profile",
    icon: User,
    nodes: ["ProfileRetrievalNode"],
  },
  {
    id: "complete",
    label: "Complete",
    icon: Sparkles,
    nodes: ["completed"],
  },
];

function getStepStatus(
  stepIndex: number,
  currentStepIndex: number,
  status: string | null
): "completed" | "active" | "pending" | "failed" {
  if (status === "failed") {
    return stepIndex <= currentStepIndex ? "failed" : "pending";
  }
  if (stepIndex < currentStepIndex) return "completed";
  if (stepIndex === currentStepIndex) return "active";
  return "pending";
}

function getCurrentStepIndex(node: string | null, status: string | null): number {
  if (status === "completed") return STEPS.length - 1;
  if (status === "failed") return STEPS.findIndex((s) => s.nodes.includes(node || "")) || 0;
  
  for (let i = STEPS.length - 1; i >= 0; i--) {
    if (STEPS[i].nodes.includes(node || "") || STEPS[i].nodes.includes(status || "")) {
      return i;
    }
  }
  return 0;
}

function ProcessingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id") ?? "";
  const nextUrl = searchParams.get("next") ?? "/onboarding/chat";

  const { status, node, message, error_message, isConnected } =
    useRunStatus(runId, !!runId);

  const currentStepIndex = useMemo(
    () => getCurrentStepIndex(node, status),
    [node, status]
  );

  const progressValue = useMemo(() => {
    if (status === "completed") return 100;
    if (status === "failed") return (currentStepIndex / (STEPS.length - 1)) * 100;
    return ((currentStepIndex + 0.5) / STEPS.length) * 100;
  }, [currentStepIndex, status]);

  useEffect(() => {
    if (status === "completed") {
      // Add a small delay to ensure the user sees the "Complete" status before navigating
      const timer = setTimeout(() => {
        router.replace(nextUrl);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [status, nextUrl, router]);

  if (!runId) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="text-destructive">Missing run ID</CardTitle>
          <CardDescription>
            No workflow run was specified. Please start from the review step.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => router.push("/onboarding/review")}>
            Back to Review
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Show error state
  if (status === "failed") {
    return (
      <Card className="w-full border-destructive/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-destructive" />
            <CardTitle>Processing failed</CardTitle>
          </div>
          <CardDescription>
            {error_message ||
              "The profiling workflow did not complete successfully."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Button onClick={() => router.push("/onboarding/review")}>
            Back to Review
          </Button>
          <Button variant="outline" onClick={() => router.push("/dashboard")}>
            Go to Dashboard
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {status === "completed" ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          )}
          Building your profile
        </CardTitle>
        <CardDescription>
          We&apos;re parsing your CV and building your profile. This usually takes a
          few minutes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-8">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{Math.round(progressValue)}%</span>
          </div>
          <Progress value={progressValue} className="h-2" />
        </div>

        {/* Steps */}
        <div className="space-y-4">
          {STEPS.map((step, index) => {
            const stepStatus = getStepStatus(index, currentStepIndex, status);
            const Icon = step.icon;
            
            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center gap-4 rounded-lg border p-4 transition-all",
                  stepStatus === "completed" && "border-green-500/30 bg-green-500/5",
                  stepStatus === "active" && "border-primary/50 bg-primary/5",
                  stepStatus === "failed" && "border-destructive/30 bg-destructive/5",
                  stepStatus === "pending" && "border-muted bg-muted/30 opacity-60"
                )}
              >
                <div
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                    stepStatus === "completed" && "bg-green-500 text-white",
                    stepStatus === "active" && "bg-primary text-primary-foreground",
                    stepStatus === "failed" && "bg-destructive text-white",
                    stepStatus === "pending" && "bg-muted text-muted-foreground"
                  )}
                >
                  {stepStatus === "completed" ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : stepStatus === "active" ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : stepStatus === "failed" ? (
                    <XCircle className="h-5 w-5" />
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                </div>
                <div className="flex-1">
                  <p
                    className={cn(
                      "font-medium",
                      stepStatus === "completed" && "text-green-600 dark:text-green-400",
                      stepStatus === "active" && "text-foreground",
                      stepStatus === "failed" && "text-destructive",
                      stepStatus === "pending" && "text-muted-foreground"
                    )}
                  >
                    {step.label}
                  </p>
                  {stepStatus === "active" && message && (
                    <p className="text-sm text-muted-foreground">{message}</p>
                  )}
                </div>
                {stepStatus === "active" && isConnected && (
                  <div className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ProcessingPage() {
  return (
    <Suspense
      fallback={
        <Card className="w-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading...
            </CardTitle>
          </CardHeader>
        </Card>
      }
    >
      <ProcessingContent />
    </Suspense>
  );
}
