import { Suspense } from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";
import { OnboardingToast } from "@/components/dashboard/OnboardingToast";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";

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
    <SidebarProvider>
      <DashboardSidebar
        user={{
          name: session.user.name,
          email: session.user.email,
          image: session.user.image,
        }}
      />
      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <span className="text-sm text-muted-foreground">Dashboard</span>
        </header>
        <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
          <Suspense fallback={null}>
            <OnboardingToast />
          </Suspense>
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
