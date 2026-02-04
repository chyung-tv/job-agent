"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { usePathname } from "next/navigation";
import Link from "next/link";


const steps = [
  { id: "identity", label: "Identity", path: "/onboarding/identity" },
  { id: "uploads", label: "Uploads", path: "/onboarding/uploads" },
  { id: "review", label: "Review", path: "/onboarding/review" },
  { id: "processing", label: "Processing", path: "/onboarding/processing" },
  { id: "chat", label: "Chat", path: "/onboarding/chat" },
  { id: "profile", label: "Profile", path: "/onboarding/profile" },
];

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const currentStepIndex = steps.findIndex(
    (step) => step.path === pathname || pathname.startsWith(step.path + "/")
  );

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
      <div className="w-full max-w-2xl space-y-8">
        {/* Stepper Navigation */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center flex-1">
                  <Link href={step.path}>
                    <Button
                      variant={
                        index === currentStepIndex
                          ? "default"
                          : index < currentStepIndex
                          ? "default"
                          : "outline"
                      }
                      size="sm"
                      className="rounded-full w-10 h-10 p-0"
                      disabled={index > currentStepIndex}
                    >
                      {index + 1}
                    </Button>
                  </Link>
                  <span
                    className={`mt-2 text-xs font-medium ${
                      index === currentStepIndex
                        ? "text-primary"
                        : index < currentStepIndex
                        ? "text-muted-foreground"
                        : "text-muted-foreground"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <Separator
                    className={`mx-4 flex-1 h-0.5 ${
                      index < currentStepIndex ? "bg-primary" : "bg-muted"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Content */}
        {children}
      </div>
    </div>
  );
}
