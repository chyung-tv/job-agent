import { Suspense } from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { OnboardingToast } from "@/components/dashboard/OnboardingToast";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user) {
    redirect("/signup");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <DashboardHeader
        user={{
          name: session.user.name,
          email: session.user.email,
          image: session.user.image,
        }}
      />
      <main className="flex-1 p-4 md:p-6">
        <Suspense fallback={null}>
          <OnboardingToast />
        </Suspense>
        {children}
      </main>
    </div>
  );
}
