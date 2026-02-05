import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { MapPin, Mail, FileText, Briefcase, User, RefreshCw, MessageCircle } from "lucide-react";

interface ProfileCardProps {
  user: {
    name: string;
    email: string;
    image: string | null;
    location: string | null;
    profileText: string | null;
    suggestedJobTitles: string[] | null;
    sourcePdfs: string[] | null;
  };
}

export function ProfileCard({ user }: ProfileCardProps) {
  return (
    <div className="grid gap-6 md:grid-cols-3">
      {/* Basic Info Card */}
      <Card className="md:col-span-1">
        <CardHeader>
          <CardTitle className="text-lg">Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-center">
            {user.image ? (
              <img
                src={user.image}
                alt={user.name}
                className="h-24 w-24 rounded-full"
              />
            ) : (
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-muted">
                <User className="h-12 w-12 text-muted-foreground" />
              </div>
            )}
          </div>
          <div className="text-center">
            <h3 className="text-lg font-semibold">{user.name}</h3>
          </div>
          <Separator />
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{user.email}</span>
            </div>
            {user.location && (
              <div className="flex items-center gap-2 text-sm">
                <MapPin className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">{user.location}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Profile Details Card */}
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle className="text-lg">Career Profile</CardTitle>
          <CardDescription>
            Your AI-generated career profile based on your CV and preferences.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Suggested Job Titles */}
          {user.suggestedJobTitles && user.suggestedJobTitles.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Briefcase className="h-4 w-4 text-muted-foreground" />
                <h4 className="text-sm font-medium">Suggested Job Titles</h4>
              </div>
              <div className="flex flex-wrap gap-2">
                {user.suggestedJobTitles.map((title, index) => (
                  <span
                    key={index}
                    className="rounded-full bg-primary/10 px-3 py-1 text-sm text-primary"
                  >
                    {title}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Profile Text */}
          {user.profileText && (
            <div>
              <div className="mb-2 flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <h4 className="text-sm font-medium">Profile Summary</h4>
              </div>
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {user.profileText}
                </p>
              </div>
            </div>
          )}

          {/* Source Documents */}
          {user.sourcePdfs && user.sourcePdfs.length > 0 && (
            <div>
              <div className="mb-2 flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <h4 className="text-sm font-medium">Source Documents</h4>
              </div>
              <ul className="space-y-2">
                {user.sourcePdfs.map((url, index) => {
                  // Extract filename from URL
                  const filename = url.split("/").pop() || `Document ${index + 1}`;
                  return (
                    <li key={index}>
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
                      >
                        <FileText className="h-4 w-4" />
                        {decodeURIComponent(filename)}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex gap-2 border-t pt-6">
          <Button variant="outline" asChild>
            <Link href="/onboarding/identity">
              <RefreshCw className="mr-2 h-4 w-4" />
              Re-do Onboarding
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/onboarding/chat">
              <MessageCircle className="mr-2 h-4 w-4" />
              Refine Profile
            </Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
