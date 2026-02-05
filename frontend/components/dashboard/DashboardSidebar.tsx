"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  User,
  Briefcase,
  LogOut,
  Search,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { ChevronUp } from "lucide-react";

interface DashboardSidebarProps {
  user?: {
    name?: string | null;
    email?: string | null;
    image?: string | null;
  };
}

const navItems = [
  {
    title: "Overview",
    href: "/dashboard/overview",
    icon: LayoutDashboard,
  },
  {
    title: "Profile",
    href: "/dashboard/profile",
    icon: User,
  },
  {
    title: "Search Jobs",
    href: "/dashboard/search",
    icon: Search,
  },
  {
    title: "Matches",
    href: "/dashboard/matches",
    icon: Briefcase,
  },
];

export function DashboardSidebar({ user }: DashboardSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { state } = useSidebar();
  const collapsed = state === "collapsed";

  const handleSignOut = async () => {
    await authClient.signOut();
    router.push("/");
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 border-b px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Briefcase className="h-4 w-4" />
          </div>
          {!collapsed && (
            <span className="font-semibold truncate">Job Agent</span>
          )}
        </div>
      </SidebarHeader>
      
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={pathname === item.href || pathname.startsWith(item.href + "/")}
                    tooltip={item.title}
                  >
                    <Link href={item.href}>
                      <item.icon className="size-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <Avatar className="h-8 w-8 rounded-lg">
                    {user?.image ? (
                      <AvatarImage src={user.image} alt={user.name || "User"} />
                    ) : null}
                    <AvatarFallback className="rounded-lg">
                      {user?.name?.charAt(0) || <User className="h-4 w-4" />}
                    </AvatarFallback>
                  </Avatar>
                  {!collapsed && (
                    <>
                      <div className="grid flex-1 text-left text-sm leading-tight">
                        <span className="truncate font-semibold">{user?.name || "User"}</span>
                        <span className="truncate text-xs">{user?.email}</span>
                      </div>
                      <ChevronUp className="ml-auto size-4" />
                    </>
                  )}
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
              >
                <DropdownMenuItem onClick={handleSignOut}>
                  <LogOut className="mr-2 h-4 w-4" />
                  <span>Sign out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
