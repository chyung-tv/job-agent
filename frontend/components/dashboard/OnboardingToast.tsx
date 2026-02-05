"use client";

import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { toast } from "sonner";

/**
 * Client component that checks for needsOnboarding query param
 * and shows a toast prompting user to complete onboarding.
 */
export function OnboardingToast() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const needsOnboarding = searchParams.get("needsOnboarding") === "true";

  useEffect(() => {
    if (needsOnboarding) {
      // Remove the query param from URL without triggering navigation
      const url = new URL(window.location.href);
      url.searchParams.delete("needsOnboarding");
      window.history.replaceState({}, "", url.pathname);

      // Show toast with action to go to onboarding
      toast.info("Complete Your Profile", {
        description: "Set up your profile to get personalized job matches.",
        duration: 10000,
        action: {
          label: "Start Onboarding",
          onClick: () => router.push("/onboarding/identity"),
        },
      });
    }
  }, [needsOnboarding, router]);

  return null;
}
