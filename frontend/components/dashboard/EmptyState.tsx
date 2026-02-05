import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Inbox, ArrowRight, Sparkles } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
  icon?: React.ComponentType<{ className?: string }>;
  className?: string;
}

export function EmptyState({
  title,
  description,
  actionLabel,
  actionHref,
  icon: Icon = Inbox,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 text-center",
        className
      )}
    >
      {/* Decorative background */}
      <div className="relative">
        <div className="absolute -inset-4 rounded-full bg-linear-to-br from-primary/10 via-primary/5 to-transparent blur-xl" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-full border border-primary/10 bg-linear-to-br from-muted to-muted/50">
          <Icon className="h-10 w-10 text-muted-foreground/60" />
        </div>
      </div>
      
      <h3 className="mt-6 text-lg font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground leading-relaxed">
        {description}
      </p>
      
      {actionLabel && actionHref && (
        <Button asChild className="mt-6 gap-1.5 group">
          <Link href={actionHref}>
            <Sparkles className="h-4 w-4" />
            {actionLabel}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </Button>
      )}
    </div>
  );
}
