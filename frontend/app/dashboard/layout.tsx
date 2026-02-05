import { Suspense } from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import { SimpleSidebar } from "@/components/dashboard/SimpleSidebar";
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
    <div className="min-h-screen">
      <SimpleSidebar
        user={{
          name: session.user.name,
          email: session.user.email,
          image: session.user.image,
        }}
      />
      {/* Main content - offset by sidebar width on desktop */}
      <main 
        id="main-content" 
        className="transition-[margin-left] duration-200 ease-in-out"
        style={{ marginLeft: "var(--sidebar-width, 0)" }}
      >
        <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b bg-background px-4 md:px-6">
          {/* Space for menu button on mobile */}
          <div className="w-10 md:w-0" />
          <span className="text-sm text-muted-foreground">Dashboard</span>
        </header>
        <div className="p-4 md:p-6">
          <Suspense fallback={null}>
            <OnboardingToast />
          </Suspense>
          {children}
        </div>
      </main>
    </div>
  );
}
