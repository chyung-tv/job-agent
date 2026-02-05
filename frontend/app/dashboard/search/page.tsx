"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Search, Sparkles, Loader2 } from "lucide-react";
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
import { EmptyState } from "@/components/dashboard/EmptyState";
import {
  getCurrentUserWithProfile,
  type UserWithProfile,
} from "@/actions/user";
import {
  triggerJobSearch,
  triggerJobSearchFromProfile,
} from "@/actions/workflow";

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
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const hasProfile = !!user?.profile_text;
  const suggestedJobTitles = user?.suggested_job_titles || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Search Jobs</h1>
        <p className="text-muted-foreground">
          Search for jobs using a custom query or your profile&apos;s suggested titles.
        </p>
      </div>

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
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="h-5 w-5" />
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
                    disabled={searching}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="location">Location</Label>
                  <Input
                    id="location"
                    placeholder="e.g. Hong Kong"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    disabled={searching}
                  />
                </div>
                <Button type="submit" className="w-full" disabled={searching}>
                  {searching ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="mr-2 h-4 w-4" />
                      Search Jobs
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Search from Profile Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5" />
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
                      Click on a title to search for that specific job, or use the button below to search all.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {suggestedJobTitles.map((title, index) => (
                        <button
                          key={index}
                          onClick={() => handleSingleJobTitleSearch(title)}
                          disabled={searching || searchingFromProfile}
                          className="rounded-full bg-primary/10 px-3 py-1 text-sm text-primary transition-colors hover:bg-primary/20 disabled:opacity-50"
                        >
                          {title}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="pt-2">
                    <Button
                      onClick={handleSearchFromProfile}
                      variant="outline"
                      className="w-full"
                      disabled={searching || searchingFromProfile}
                    >
                      {searchingFromProfile ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Starting searches...
                        </>
                      ) : (
                        <>
                          <Sparkles className="mr-2 h-4 w-4" />
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
                <p className="text-xs text-muted-foreground">
                  Location: {user.location}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
