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
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
  const initials = user.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="grid gap-6 md:grid-cols-3">
      {/* Basic Info Card */}
      <Card className="group md:col-span-1 transition-all duration-200 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20">
        <CardHeader>
          <CardTitle className="text-lg">Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-center">
            <Avatar className="h-24 w-24 border-2 border-primary/10">
              <AvatarImage src={user.image || undefined} alt={user.name} />
              <AvatarFallback className="bg-primary/10 text-primary text-2xl font-semibold">
                {initials}
              </AvatarFallback>
            </Avatar>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-semibold">{user.name}</h3>
          </div>
          <Separator />
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Mail className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground truncate">{user.email}</span>
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
      <Card className="group md:col-span-2 transition-all duration-200 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20">
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
              <div className="mb-3 flex items-center gap-2">
                <Briefcase className="h-4 w-4 text-primary" />
                <h4 className="text-sm font-medium">Suggested Job Titles</h4>
              </div>
              <div className="flex flex-wrap gap-2">
                {user.suggestedJobTitles.map((title, index) => (
                  <Badge
                    key={index}
                    variant="secondary"
                    className="font-normal"
                  >
                    {title}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Profile Text */}
          {user.profileText && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <User className="h-4 w-4 text-primary" />
                <h4 className="text-sm font-medium">Profile Summary</h4>
              </div>
              <ScrollArea className="h-[200px] rounded-lg border bg-muted/30 p-4">
                <p className="whitespace-pre-wrap text-sm text-muted-foreground leading-relaxed">
                  {user.profileText}
                </p>
              </ScrollArea>
            </div>
          )}

          {/* Source Documents */}
          {user.sourcePdfs && user.sourcePdfs.length > 0 && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
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
          <Button variant="outline" asChild className="gap-1.5">
            <Link href="/onboarding/identity">
              <RefreshCw className="h-4 w-4" />
              Re-do Onboarding
            </Link>
          </Button>
          <Button variant="outline" asChild className="gap-1.5">
            <Link href="/onboarding/chat">
              <MessageCircle className="h-4 w-4" />
              Refine Profile
            </Link>
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
