"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authClient } from "@/lib/auth-client";
import { useOnboardingStore } from "@/store/useOnboardingStore";
import { UploadDropzone } from "@/lib/uploadthing";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, XCircle } from "lucide-react";

/**
 * Hook to check if client-side hydration is complete.
 * Prevents hydration mismatches when using Zustand with sessionStorage.
 */
function useHasHydrated() {
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  return hasHydrated;
}

type OnboardingStep = "identity" | "cv-upload" | "review";

export default function OnboardingPage() {
  const router = useRouter();
  const hasHydrated = useHasHydrated();
  const [isLoading, setIsLoading] = useState(true);
  const [session, setSession] = useState<any>(null);
  const [location, setLocation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentStep, setCurrentStep] = useState<OnboardingStep>("identity");

  const {
    name: storeName,
    email: storeEmail,
    location: storeLocation,
    cv_urls,
    setName,
    setEmail,
    setLocation: setStoreLocation,
    addCvUrl,
  } = useOnboardingStore();

  // Debug: log key state on each render
  console.log("OnboardingPage render", {
    currentStep,
    hasHydrated,
    isLoading,
    storeName,
    storeEmail,
    storeLocation,
    cv_urls_count: cv_urls.length,
  });

  // Fetch session on mount
  useEffect(() => {
    async function fetchSession() {
      try {
        const sessionData = await authClient.getSession();
        setSession(sessionData?.data?.user || null);
        
        // Pre-fill from session if available
        if (sessionData?.data?.user) {
          const user = sessionData.data.user;
          if (user.name && !storeName) {
            setName(user.name);
          }
          if (user.email && !storeEmail) {
            setEmail(user.email);
          }
        }
        
        // Pre-fill location from store if available
        if (storeLocation) {
          setLocation(storeLocation);
        }
      } catch (error) {
        console.error("Failed to fetch session:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchSession();
  }, [setName, setEmail, storeName, storeEmail, storeLocation]);

  const handleIdentitySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!location.trim()) {
      alert("Please enter your location");
      return;
    }

    setIsSubmitting(true);
    
    try {
      // Save to store
      setStoreLocation(location.trim());
      
      // Navigate to CV upload step
      setCurrentStep("cv-upload");
    } catch (error) {
      console.error("Failed to save onboarding data:", error);
      alert("Failed to save. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCvUploadComplete = (files: Array<{ url: string; name: string }>) => {
    console.log("UploadThing result:", files);
    files.forEach((file) => {
      if (file.url) {
        console.log("Adding CV URL:", file.url);
        addCvUrl(file.url);
      } else {
        console.warn("File missing URL:", file);
      }
    });
    // Force a re-render check - use getState() from the store
    setTimeout(() => {
      const currentUrls = useOnboardingStore.getState().cv_urls;
      console.log("CV URLs after upload:", currentUrls);
    }, 100);
  };

  const handleReviewContinue = () => {
    // Check all requirements are met
    const allChecked = 
      storeName && 
      storeEmail && 
      storeLocation && 
      cv_urls.length > 0;

    if (allChecked) {
      // Console.log the CV URLs as specified
      console.log("CV URLs from store:", cv_urls);
      console.log("Final CV URLs:", JSON.stringify(cv_urls, null, 2));
      
      // For now, just show success - later we'll submit to API
      alert("All files checked! CV URLs logged to console.");
    }
  };

  // Check if all requirements are met for review step
  const checklistItems = {
    name: !!storeName,
    email: !!storeEmail,
    location: !!storeLocation,
    cvUploaded: cv_urls.length > 0,
  };

  const allChecked = Object.values(checklistItems).every(Boolean);

  // Show loading state until hydrated and session fetched
  if (!hasHydrated || isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <p className="text-center text-muted-foreground">Loading...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Pre-fill from store or session
  const displayName = storeName || session?.name || "";
  const displayEmail = storeEmail || session?.email || "";

  // Render Identity Step
  if (currentStep === "identity") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">Welcome to Job Agent</CardTitle>
            <CardDescription>
              Let's get started by setting up your profile
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleIdentitySubmit}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  type="text"
                  value={displayName}
                  disabled
                  className="bg-muted"
                  placeholder="Your name"
                />
                <p className="text-xs text-muted-foreground">
                  Pre-filled from your account
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={displayEmail}
                  disabled
                  className="bg-muted"
                  placeholder="your.email@example.com"
                />
                <p className="text-xs text-muted-foreground">
                  Pre-filled from your account
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="location">
                  Location <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="location"
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  required
                  placeholder="e.g., Hong Kong, New York, Remote"
                  disabled={isSubmitting}
                />
                <p className="text-xs text-muted-foreground">
                  This helps us find jobs in your preferred location
                </p>
              </div>
            </CardContent>
            <CardFooter className="flex flex-col space-y-4">
              <Button
                type="submit"
                className="w-full"
                disabled={isSubmitting || !location.trim()}
              >
                {isSubmitting ? "Saving..." : "Continue"}
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                Your information is saved locally and will be used to create your profile
              </p>
            </CardFooter>
          </form>
        </Card>
      </div>
    );
  }

  // Render CV Upload Step
  if (currentStep === "cv-upload") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold">Upload Your CV</CardTitle>
            <CardDescription>
              Upload your CV/Resume as a PDF file (max 4MB)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {process.env.NEXT_PUBLIC_API_URL && (
              <p className="text-xs text-muted-foreground">
                Debug: Upload endpoint <code>/api/uploadthing</code> is mounted. Select a PDF to start upload.
              </p>
            )}
            <UploadDropzone
              endpoint="pdfUploader"
              onClientUploadComplete={(res) => {
                // Do something with the response
                console.log("Files: ", res);
                alert("Upload Completed");
                if (res && Array.isArray(res) && res.length > 0) {
                  const files = res.map((file: { url: string; name?: string }) => ({
                    url: file.url,
                    name: file.name || "CV.pdf",
                  }));
                  handleCvUploadComplete(files);
                }
              }}
              onUploadError={(error: Error) => {
                // Do something with the error.
                alert(`ERROR! ${error.message}`);
              }}
            />
            {cv_urls.length > 0 && (
              <div className="mt-4 space-y-2">
                <Label>Uploaded Files:</Label>
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                  {cv_urls.map((url, index) => (
                    <li key={index}>
                      <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        CV {index + 1}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <div className="flex flex-col gap-2 w-full sm:flex-row">
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => setCurrentStep("identity")}
              >
                Back
              </Button>
              <Button
                type="button"
                className="w-full"
                onClick={() => setCurrentStep("review")}
                disabled={cv_urls.length === 0}
              >
                Continue
              </Button>
            </div>
          </CardFooter>
        </Card>
      </div>
    );
  }

  // Render Review/Checklist Step
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold">Review Your Information</CardTitle>
          <CardDescription>
            Please verify all information is correct before proceeding
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              {checklistItems.name ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={checklistItems.name ? "text-foreground" : "text-muted-foreground"}>
                Name provided
              </span>
            </div>
            <div className="flex items-center gap-2">
              {checklistItems.email ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={checklistItems.email ? "text-foreground" : "text-muted-foreground"}>
                Email provided
              </span>
            </div>
            <div className="flex items-center gap-2">
              {checklistItems.location ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={checklistItems.location ? "text-foreground" : "text-muted-foreground"}>
                Location provided
              </span>
            </div>
            <div className="flex items-center gap-2">
              {checklistItems.cvUploaded ? (
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={checklistItems.cvUploaded ? "text-foreground" : "text-muted-foreground"}>
                At least one CV uploaded ({cv_urls.length} file{cv_urls.length !== 1 ? "s" : ""})
              </span>
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          <div className="flex gap-2 w-full">
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => setCurrentStep("cv-upload")}
            >
              Back
            </Button>
            <Button
              type="button"
              className="w-full"
              onClick={handleReviewContinue}
              disabled={!allChecked}
            >
              Continue
            </Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}
