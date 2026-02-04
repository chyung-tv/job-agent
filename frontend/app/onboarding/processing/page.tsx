"use client";

import { triggerProfiling } from "@/actions/workflow";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useRunStatus } from "@/hooks/useRunStatus";
import { useOnboardingStore } from "@/store/useOnboardingStore";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, useRef } from "react";

const STEP_LABELS: Record<string, string> = {
  pending: "Submitted",
  UserInputNode: "Processing",
  CVProcessingNode: "Parsing CV",
  ProfileRetrievalNode: "Building profile",
  processing: "Processing",
  completed: "Complete",
  failed: "Failed",
};

function getStepLabel(node: string | null, status: string | null): string {
  if (node && STEP_LABELS[node]) return STEP_LABELS[node];
  if (status && STEP_LABELS[status]) return STEP_LABELS[status];
  return status === "processing" || status === "pending"
    ? "Processing..."
    : node || status || "Submitted";
}

function ProcessingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id") ?? "";
  const nextUrl = searchParams.get("next") ?? "/onboarding/chat";

  const { status, node, message, error_message, isConnected } =
    useRunStatus(runId, !!runId);

  // Retry state management
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const hasRetriedRef = useRef(false);
  const currentRunIdRef = useRef<string>("");

  // Reset retry state when runId changes
  useEffect(() => {
    if (currentRunIdRef.current !== runId) {
      currentRunIdRef.current = runId;
      hasRetriedRef.current = false;
      setRetryCount(0);
      setIsRetrying(false);
      setRetryError(null);
    }
  }, [runId]);

  // Get onboarding store data for retry
  const { name, email, location, cv_files, basic_info } = useOnboardingStore();

  // Detect event loop cleanup error
  const isEventLoopCleanupError = useMemo(
    () =>
      status === "failed" &&
      typeof error_message === "string" &&
      error_message.includes(
        "Event loop closed during httpx/httpcore connection cleanup"
      ),
    [status, error_message]
  );

  const isSoftSuccess = useMemo(
    () =>
      status === "completed" &&
      typeof error_message === "string" &&
      error_message.includes(
        "async HTTP client cleanup error (event loop closed during httpx/httpcore cleanup)"
      ),
    [status, error_message]
  );

  // Automatic retry logic for event loop cleanup error
  useEffect(() => {
    if (
      isEventLoopCleanupError &&
      retryCount < 1 &&
      !isRetrying &&
      !hasRetriedRef.current &&
      name &&
      email &&
      location &&
      cv_files.length > 0
    ) {
      hasRetriedRef.current = true;
      setIsRetrying(true);
      setRetryError(null);
      setRetryCount((prev) => prev + 1);

      const retryProfiling = async () => {
        try {
          const response = await triggerProfiling({
            name,
            email,
            location,
            cv_urls: cv_files.map((f) => f.url),
            ...(basic_info ? { basic_info } : {}),
          });

          // Navigate to new run_id
          const newNextUrl = searchParams.get("next") ?? "/onboarding/chat";
          router.replace(
            `/onboarding/processing?run_id=${response.run_id}&next=${encodeURIComponent(newNextUrl)}`
          );
          setIsRetrying(false);
        } catch (error) {
          console.error("Retry failed:", error);
          setRetryError(
            error instanceof Error ? error.message : "Failed to retry"
          );
          setIsRetrying(false);
        }
      };

      retryProfiling();
    }
  }, [
    isEventLoopCleanupError,
    retryCount,
    isRetrying,
    name,
    email,
    location,
    cv_files,
    basic_info,
    router,
    searchParams,
  ]);

  useEffect(() => {
    if (status === "completed") {
      // Add a small delay to ensure the user sees the "Complete" status before navigating
      const timer = setTimeout(() => {
        router.replace(nextUrl);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [status, nextUrl, router]);

  if (!runId) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Missing run ID</CardTitle>
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

  // Show retrying state
  if (isRetrying) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Retrying...</CardTitle>
          <CardDescription>
            The previous attempt encountered a temporary issue. Automatically retrying
            (attempt {retryCount}/2)...
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 animate-pulse rounded-full bg-blue-500" />
            <span className="text-sm text-muted-foreground">
              Submitting retry request...
            </span>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Show error state (only if not retrying and either not a retryable error or already retried)
  if (
    status === "failed" &&
    (!isEventLoopCleanupError || retryCount >= 1 || retryError)
  ) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Processing failed</CardTitle>
          <CardDescription>
            {retryError ||
              error_message ||
              "The profiling workflow did not complete successfully."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {retryCount >= 1 && (
            <div className="rounded-md border border-yellow-500/50 bg-yellow-50 dark:bg-yellow-900/20 p-3">
              <p className="text-sm text-yellow-800 dark:text-yellow-200">
                Automatic retry was attempted but failed. Please try again manually.
              </p>
            </div>
          )}
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

  const currentLabel = getStepLabel(node, status);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Building your profile</CardTitle>
        <CardDescription>
          We're parsing your CV and building your profile. This usually takes a
          few minutes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {isSoftSuccess && (
          <div className="rounded-md border border-yellow-500/50 bg-yellow-50 dark:bg-yellow-900/20 p-3">
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              Profile completed with a minor issue
            </p>
            <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-300">
              We finished building your profile, but there was a minor background cleanup issue. Your answers and profile have been saved.
            </p>
          </div>
        )}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div
              className={`h-3 w-3 rounded-full ${
                isConnected ? "animate-pulse bg-green-500" : "bg-muted"
              }`}
            />
            <span className="text-sm font-medium">{currentLabel}</span>
          </div>
          {message && (
            <p className="text-sm text-muted-foreground">{message}</p>
          )}
        </div>
        <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
          <li className={status !== "pending" ? "text-foreground" : ""}>
            Submitted
          </li>
          <li
            className={
              node === "CVProcessingNode" || status === "processing"
                ? "text-foreground"
                : ""
            }
          >
            Parsing CV
          </li>
          <li
            className={
              node === "ProfileRetrievalNode" || status === "completed"
                ? "text-foreground"
                : ""
            }
          >
            Building profile
          </li>
          <li className={status === "completed" ? "text-foreground" : ""}>
            Complete
          </li>
        </ul>
      </CardContent>
    </Card>
  );
}

export default function ProcessingPage() {
  return (
    <Suspense fallback={<Card className="w-full"><CardHeader><CardTitle>Loading...</CardTitle></CardHeader></Card>}>
      <ProcessingContent />
    </Suspense>
  );
}
