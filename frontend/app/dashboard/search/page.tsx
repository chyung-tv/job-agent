"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Search, Sparkles, Loader2, MapPin, AlertTriangle } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { EmptyState } from "@/components/dashboard/EmptyState";
import {
  getCurrentUserWithProfile,
  type UserWithProfile,
} from "@/actions/user";
import {
  triggerJobSearch,
  triggerJobSearchFromProfile,
} from "@/actions/workflow";
import { cn } from "@/lib/utils";

export default function SearchPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserWithProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [searchingFromProfile, setSearchingFromProfile] = useState(false);

  // Form state
  const [jobTitle, setJobTitle] = useState("");
  const [location, setLocation] = useState("");

  // Load user profile on mount
  useEffect(() => {
    async function loadUser() {
      try {
        const userData = await getCurrentUserWithProfile();
        setUser(userData);
        if (userData?.location) {
          setLocation(userData.location);
        }
      } catch (error) {
        console.error("Failed to load user profile:", error);
        toast.error("Failed to load profile");
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  const handleCustomSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobTitle.trim() || !location.trim()) {
      toast.error("Please enter both job title and location");
      return;
    }
    if (!user?.id) {
      toast.error("User not found");
      return;
    }

    setSearching(true);
    try {
      const response = await triggerJobSearch({
        query: jobTitle.trim(),
        location: location.trim(),
        user_id: user.id,
      });
      toast.success(`Job search started! Run ID: ${response.run_id.slice(0, 8)}...`);
      router.push("/dashboard/overview");
    } catch (error) {
      console.error("Job search failed:", error);
      toast.error(error instanceof Error ? error.message : "Job search failed");
    } finally {
      setSearching(false);
    }
  };

  const handleSingleJobTitleSearch = async (title: string) => {
    if (!user?.id || !user?.location) {
      toast.error("User profile incomplete - missing location");
      return;
    }

    setSearching(true);
    try {
      const response = await triggerJobSearch({
        query: title,
        location: user.location,
        user_id: user.id,
      });
      toast.success(`Searching for "${title}"! Run ID: ${response.run_id.slice(0, 8)}...`);
      router.push("/dashboard/overview");
    } catch (error) {
      console.error("Job search failed:", error);
      toast.error(error instanceof Error ? error.message : "Job search failed");
    } finally {
      setSearching(false);
    }
  };

  const handleSearchFromProfile = async () => {
    if (!user?.id) {
      toast.error("User not found");
      return;
    }

    setSearchingFromProfile(true);
    try {
      const response = await triggerJobSearchFromProfile({
        user_id: user.id,
      });
      toast.success(
        `Started ${response.job_titles_count} job searches for: ${response.job_titles.join(", ")}`
      );
      router.push("/dashboard/overview");
    } catch (error) {
      console.error("Job search from profile failed:", error);
      toast.error(
        error instanceof Error ? error.message : "Job search from profile failed"
      );
    } finally {
      setSearchingFromProfile(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading your profile...</p>
        </div>
      </div>
    );
  }

  const hasProfile = !!user?.profile_text;
  const suggestedJobTitles = user?.suggested_job_titles || [];
  const hasAccess = user?.hasAccess ?? false;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Search Jobs</h1>
        <p className="text-muted-foreground">
          Search for jobs using a custom query or your profile&apos;s suggested titles.
        </p>
      </div>

      {/* Beta Access Required Banner */}
      {!hasAccess && hasProfile && (
        <Alert className="border-amber-500 bg-amber-50 dark:bg-amber-950/20">
          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-500" />
          <AlertTitle className="text-amber-800 dark:text-amber-200">
            Beta Access Required
          </AlertTitle>
          <AlertDescription className="text-amber-700 dark:text-amber-300">
            This feature is currently in beta. To request access, please email{" "}
            <a
              href="mailto:chyung.tv@gmail.com"
              className="font-medium underline hover:text-amber-900 dark:hover:text-amber-100"
            >
              chyung.tv@gmail.com
            </a>
          </AlertDescription>
        </Alert>
      )}

      {!hasProfile ? (
        <EmptyState
          title="Profile not set up"
          description="Complete the onboarding process to enable job search with personalized suggestions."
          actionLabel="Start Onboarding"
          actionHref="/onboarding/identity"
        />
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Custom Search Card */}
          <Card className="group transition-all duration-200 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <Search className="h-4 w-4" />
                </div>
                Custom Search
              </CardTitle>
              <CardDescription>
                Search for jobs with a specific title and location.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCustomSearch} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="jobTitle">Job Title</Label>
                  <Input
                    id="jobTitle"
                    placeholder="e.g. Software Engineer"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    disabled={searching || !hasAccess}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="location">Location</Label>
                  <Input
                    id="location"
                    placeholder="e.g. Hong Kong"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    disabled={searching || !hasAccess}
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full gap-1.5"
                  disabled={searching || !hasAccess}
                >
                  {searching ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="h-4 w-4" />
                      Search Jobs
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Search from Profile Card */}
          <Card className="group transition-all duration-200 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                  <Sparkles className="h-4 w-4" />
                </div>
                Search from Profile
              </CardTitle>
              <CardDescription>
                Search jobs based on your profile&apos;s suggested titles.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {suggestedJobTitles.length > 0 ? (
                <>
                  <div>
                    <Label className="mb-2 block">Suggested Job Titles</Label>
                    <p className="mb-3 text-xs text-muted-foreground">
                      {hasAccess
                        ? "Click on a title to search for that specific job, or use the button below to search all."
                        : "Request beta access to search for jobs."}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {suggestedJobTitles.map((title, index) => (
                        <Badge
                          key={index}
                          variant="outline"
                          className={cn(
                            "transition-all",
                            hasAccess
                              ? "cursor-pointer hover:bg-primary hover:text-primary-foreground hover:border-primary"
                              : "cursor-not-allowed opacity-50"
                          )}
                          onClick={() =>
                            hasAccess && handleSingleJobTitleSearch(title)
                          }
                        >
                          {title}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="pt-2">
                    <Button
                      onClick={handleSearchFromProfile}
                      variant="outline"
                      className="w-full gap-1.5"
                      disabled={searching || searchingFromProfile || !hasAccess}
                    >
                      {searchingFromProfile ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Starting searches...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          Search All ({suggestedJobTitles.length} titles)
                        </>
                      )}
                    </Button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No suggested job titles found in your profile. Try refining your profile or using custom search.
                </p>
              )}

              {user?.location && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground pt-2 border-t">
                  <MapPin className="h-3.5 w-3.5" />
                  <span>Location: {user.location}</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
