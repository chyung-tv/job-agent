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
import { useRouter } from "next/navigation";

/**
 * Post-login redirect page.
 * 
 * Simple page that allows users to choose between going to the dashboard
 * or starting the onboarding flow after signing in.
 */
export default function RedirectPage() {
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold">Welcome!</CardTitle>
          <CardDescription>
            Choose where you would like to go next
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            You can either go to your dashboard or start the onboarding process.
          </p>
        </CardContent>
        <CardFooter className="flex flex-col space-y-4">
          <Button
            type="button"
            className="w-full"
            onClick={() => router.push("/dashboard")}
          >
            Go to Dashboard
          </Button>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => router.push("/onboarding")}
          >
            Start Onboarding
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
