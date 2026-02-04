import { getOnboardingProfile } from "@/actions/user";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import Link from "next/link";

export default async function OnboardingProfilePage() {
  const profile = await getOnboardingProfile();

  if (!profile) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Profile not found</CardTitle>
          <CardDescription>
            You may need to complete the onboarding steps first.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button asChild>
            <Link href="/onboarding/review">Go to Review</Link>
          </Button>
        </CardFooter>
      </Card>
    );
  }

  const cvLinks = profile.source_pdfs ?? [];
  const references = profile.references
    ? Object.entries(profile.references)
    : [];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Your profile</CardTitle>
        <CardDescription>
          Here’s everything we have for you. You can use the dashboard to run
          job searches and view matches.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-sm text-muted-foreground">Name</Label>
            <p className="text-sm font-medium">{profile.name || "—"}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-sm text-muted-foreground">Email</Label>
            <p className="text-sm font-medium">{profile.email || "—"}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-sm text-muted-foreground">Location</Label>
            <p className="text-sm font-medium">{profile.location || "—"}</p>
          </div>
        </div>

        {cvLinks.length > 0 && (
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">
              Uploaded CVs
            </Label>
            <ul className="list-inside space-y-1 text-sm">
              {cvLinks.map((url, i) => (
                <li key={i}>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    {typeof url === "string" ? url.split("/").pop() ?? url : "CV link"}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {references.length > 0 && (
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Links</Label>
            <ul className="list-inside space-y-1 text-sm">
              {references.map(([key, value]) => (
                <li key={key}>
                  <span className="capitalize">{key}: </span>
                  {typeof value === "string" ? (
                    <a
                      href={value}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      {value}
                    </a>
                  ) : (
                    String(value)
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {profile.profile_text && (
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">
              Agent-generated profile
            </Label>
            <div className="rounded-md border bg-muted/30 p-4">
              <p className="whitespace-pre-wrap text-sm">
                {profile.profile_text}
              </p>
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Button asChild>
          <Link href="/dashboard">Go to Dashboard</Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
