"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Check, User, Upload, Eye, Loader2, MessageCircle, Sparkles } from "lucide-react";

const steps = [
  { id: "identity", label: "Identity", path: "/onboarding/identity", icon: User },
  { id: "uploads", label: "Uploads", path: "/onboarding/uploads", icon: Upload },
  { id: "review", label: "Review", path: "/onboarding/review", icon: Eye },
  { id: "processing", label: "Processing", path: "/onboarding/processing", icon: Loader2 },
  { id: "chat", label: "Chat", path: "/onboarding/chat", icon: MessageCircle },
  { id: "profile", label: "Profile", path: "/onboarding/profile", icon: Sparkles },
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
    <div className="flex min-h-screen items-center justify-center bg-linear-to-b from-background to-muted/30 px-4 py-12">
      <div className="w-full max-w-2xl space-y-8">
        {/* Stepper Navigation */}
        <Card className="p-6 shadow-lg">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => {
              const isCompleted = index < currentStepIndex;
              const isCurrent = index === currentStepIndex;
              const isPending = index > currentStepIndex;
              const Icon = step.icon;

              return (
                <div key={step.id} className="flex items-center flex-1">
                  <div className="flex flex-col items-center flex-1">
                    <Link 
                      href={step.path}
                      className={cn(
                        isPending && "pointer-events-none"
                      )}
                    >
                      <Button
                        variant={isCompleted || isCurrent ? "default" : "outline"}
                        size="icon"
                        className={cn(
                          "rounded-full w-10 h-10 transition-all",
                          isCompleted && "bg-green-500 hover:bg-green-600",
                          isCurrent && "ring-2 ring-primary ring-offset-2 ring-offset-background",
                          isPending && "opacity-50"
                        )}
                        disabled={isPending}
                      >
                        {isCompleted ? (
                          <Check className="h-5 w-5" />
                        ) : (
                          <Icon className={cn(
                            "h-4 w-4",
                            isCurrent && step.id === "processing" && "animate-spin"
                          )} />
                        )}
                      </Button>
                    </Link>
                    <span
                      className={cn(
                        "mt-2 text-xs font-medium transition-colors",
                        isCompleted && "text-green-600 dark:text-green-400",
                        isCurrent && "text-primary",
                        isPending && "text-muted-foreground"
                      )}
                    >
                      {step.label}
                    </span>
                  </div>
                  {index < steps.length - 1 && (
                    <div
                      className={cn(
                        "mx-2 h-0.5 flex-1 rounded-full transition-colors",
                        index < currentStepIndex ? "bg-green-500" : "bg-muted"
                      )}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        {/* Content */}
        {children}
      </div>
    </div>
  );
}
