import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { RunsTable } from "@/components/dashboard/RunsTable";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, CheckCircle2, Briefcase, Clock } from "lucide-react";

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

  // Calculate stats
  const totalRuns = runs.length;
  const completedRuns = runs.filter((r) => r.status === "completed").length;
  const pendingRuns = runs.filter((r) => r.status === "pending" || r.status === "processing").length;
  const totalMatches = runs.reduce((sum, r) => sum + r.total_matched_jobs, 0);

  const stats = [
    {
      title: "Total Runs",
      value: totalRuns,
      icon: Activity,
      description: "All workflow runs",
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
    },
    {
      title: "Completed",
      value: completedRuns,
      icon: CheckCircle2,
      description: "Successful runs",
      color: "text-green-500",
      bgColor: "bg-green-500/10",
    },
    {
      title: "In Progress",
      value: pendingRuns,
      icon: Clock,
      description: "Running workflows",
      color: "text-yellow-500",
      bgColor: "bg-yellow-500/10",
    },
    {
      title: "Total Matches",
      value: totalMatches,
      icon: Briefcase,
      description: "Jobs matched",
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
        <p className="text-muted-foreground">
          Track your job search workflows and their progress.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title} className="group transition-all duration-200 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <div className={`rounded-lg p-2 ${stat.bgColor} transition-transform group-hover:scale-110`}>
                <stat.icon className={`h-4 w-4 ${stat.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">{stat.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Runs Table */}
      <Card className="transition-all duration-200 hover:shadow-md hover:shadow-primary/5">
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
