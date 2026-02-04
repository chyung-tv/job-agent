"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useRunStatus } from "@/hooks/useRunStatus";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

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

  useEffect(() => {
    if (status === "completed") {
      router.replace(nextUrl);
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

  if (status === "failed") {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Processing failed</CardTitle>
          <CardDescription>
            {error_message || "The profiling workflow did not complete successfully."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
