import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { MatchCard } from "@/components/dashboard/MatchCard";
import { EmptyState } from "@/components/dashboard/EmptyState";
import { Card, CardContent } from "@/components/ui/card";

export default async function MatchesPage() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return null;
  }

  // Fetch user's matched jobs with job postings and artifacts
  const matches = await prisma.matched_jobs.findMany({
    where: { user_id: session.user.id },
    include: {
      job_postings: true,
      artifacts: true,
    },
    orderBy: { created_at: "desc" },
  });

  // Filter to only show actual matches (is_match = true)
  const actualMatches = matches.filter((m) => m.is_match);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Job Matches</h1>
        <p className="text-muted-foreground">
          Jobs that match your profile, with tailored CVs and cover letters.
        </p>
      </div>

      {actualMatches.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              title="No matches yet"
              description="Complete your profile and run a job search to find matching positions."
              actionLabel="View Profile"
              actionHref="/dashboard/profile"
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {actualMatches.map((match) => (
            <MatchCard
              key={match.id}
              match={{
                id: match.id,
                title: match.job_postings?.title || "Unknown Position",
                company: match.job_postings?.company_name || "Unknown Company",
                location: match.job_postings?.location || null,
                reason: match.reason,
                isMatch: match.is_match,
                hasArtifacts: !!match.artifacts,
                createdAt: match.created_at,
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
