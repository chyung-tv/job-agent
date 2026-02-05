import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { ProfileCard } from "@/components/dashboard/ProfileCard";
import { EmptyState } from "@/components/dashboard/EmptyState";

export default async function ProfilePage() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return null;
  }

  // Fetch user profile
  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      id: true,
      name: true,
      email: true,
      image: true,
      location: true,
      profile_text: true,
      suggested_job_titles: true,
      source_pdfs: true,
    },
  });

  if (!user) {
    return null;
  }

  // Parse JSON fields - Prisma Json returns JsonValue, so filter to strings
  const suggestedJobTitles = user.suggested_job_titles as string[] | null;
  let sourcePdfs: string[] | null = null;
  if (user.source_pdfs) {
    if (Array.isArray(user.source_pdfs)) {
      sourcePdfs = user.source_pdfs.filter((v): v is string => typeof v === "string");
    } else if (typeof user.source_pdfs === "object") {
      sourcePdfs = Object.values(user.source_pdfs as Record<string, unknown>).filter(
        (v): v is string => typeof v === "string"
      );
    }
  }

  const hasProfile = !!user.profile_text;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <p className="text-muted-foreground">
          Your master identity and career profile.
        </p>
      </div>

      {hasProfile ? (
        <ProfileCard
          user={{
            name: user.name,
            email: user.email,
            image: user.image,
            location: user.location,
            profileText: user.profile_text,
            suggestedJobTitles: Array.isArray(suggestedJobTitles) ? suggestedJobTitles : null,
            sourcePdfs: sourcePdfs,
          }}
        />
      ) : (
        <EmptyState
          title="Profile not set up"
          description="Complete the onboarding process to create your career profile and get personalized job matches."
          actionLabel="Start Onboarding"
          actionHref="/onboarding/identity"
        />
      )}
    </div>
  );
}
