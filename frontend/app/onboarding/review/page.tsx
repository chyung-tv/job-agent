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
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useOnboardingStore } from "@/store/useOnboardingStore";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function ReviewPage() {
  const router = useRouter();
  const { name, email, location, cv_files, reset } = useOnboardingStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const handleBack = () => {
    router.push("/onboarding/uploads");
  };

  const handleEditIdentity = () => {
    router.push("/onboarding/identity");
  };

  const handleEditUploads = () => {
    router.push("/onboarding/uploads");
  };

  const handleSubmit = async () => {
    try {
      setIsSubmitting(true);
      setSubmitError(null);

      // Construct payload (API expects cv_urls; we keep keys/URLs for submission)
      const payload = {
        name,
        email,
        location,
        cv_urls: cv_files.map((f) => f.url),
      };

      // Call placeholder API
      const response = await fetch("/api/placeholder", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("Failed to submit onboarding data");
      }

      setSubmitSuccess(true);

      // Clear store after successful submission
      setTimeout(() => {
        reset();
        router.push("/dashboard");
      }, 2000);
    } catch (error) {
      console.error("Submission error:", error);
      setSubmitError(
        error instanceof Error ? error.message : "Failed to submit. Please try again."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-2xl font-bold">Review Your Information</CardTitle>
        <CardDescription>
          Please review all the information before submitting
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Identity Information Section */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Identity Information</CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleEditIdentity}
                disabled={isSubmitting}
              >
                Edit
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label className="text-sm text-muted-foreground">Name</Label>
              <p className="text-sm font-medium">{name || "Not provided"}</p>
            </div>
            <div className="space-y-1">
              <Label className="text-sm text-muted-foreground">Email</Label>
              <p className="text-sm font-medium">{email || "Not provided"}</p>
            </div>
            <div className="space-y-1">
              <Label className="text-sm text-muted-foreground">Location</Label>
              <p className="text-sm font-medium">{location || "Not provided"}</p>
            </div>
          </CardContent>
        </Card>

        <Separator />

        {/* Uploaded Files Section */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Uploaded Files</CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleEditUploads}
                disabled={isSubmitting}
              >
                Edit
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {cv_files.length > 0 ? (
              <div className="space-y-2">
                {cv_files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-2 border rounded-md"
                  >
                    <span className="text-sm">{file.name}</span>
                    <a
                      href={file.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary hover:underline"
                    >
                      View
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No files uploaded</p>
            )}
          </CardContent>
        </Card>

        {/* Error Message */}
        {submitError && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
            <p className="text-sm text-destructive">{submitError}</p>
          </div>
        )}

        {/* Success Message */}
        {submitSuccess && (
          <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-md">
            <p className="text-sm text-green-600 dark:text-green-400">
              Successfully submitted! Redirecting...
            </p>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button variant="outline" onClick={handleBack} disabled={isSubmitting}>
          Back
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting || submitSuccess}>
          {isSubmitting ? "Submitting..." : submitSuccess ? "Submitted!" : "Submit"}
        </Button>
      </CardFooter>
    </Card>
  );
}
