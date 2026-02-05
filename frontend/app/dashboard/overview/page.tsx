import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default async function OverviewPage() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return null;
  }

  // Fetch user's runs
  const runs = await prisma.runs.findMany({
    where: { user_id: session.user.id },
    orderBy: { created_at: "desc" },
    take: 20,
    select: {
      id: true,
      status: true,
      task_id: true,
      error_message: true,
      total_matched_jobs: true,
      completed_at: true,
      created_at: true,
      updated_at: true,
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
        <p className="text-muted-foreground">
          Track your job search workflows and their progress.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Runs</CardTitle>
          <CardDescription>
            Your job search and profiling workflow runs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <EmptyState
              title="No runs yet"
              description="Start by completing your profile to begin searching for jobs."
              actionLabel="Complete Onboarding"
              actionHref="/onboarding/identity"
            />
          ) : (
            <RunsTable runs={runs} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
