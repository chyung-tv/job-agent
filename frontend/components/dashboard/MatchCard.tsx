import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Building2, MapPin, FileCheck, ArrowRight } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface MatchCardProps {
  match: {
    id: string;
    title: string;
    company: string;
    location: string | null;
    reason: string;
    isMatch: boolean;
    hasArtifacts: boolean;
    createdAt: Date;
  };
}

export function MatchCard({ match }: MatchCardProps) {
  return (
    <Card className="group flex flex-col transition-all duration-200 hover:shadow-md hover:shadow-primary/5 hover:border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1 space-y-1">
            <CardTitle className="line-clamp-2 text-base group-hover:text-primary transition-colors">
              {match.title}
            </CardTitle>
            <CardDescription className="flex items-center gap-1">
              <Building2 className="h-3 w-3 shrink-0" />
              <span className="truncate">{match.company}</span>
            </CardDescription>
          </div>
          {match.hasArtifacts && (
            <Badge
              variant="outline"
              className="shrink-0 gap-1 border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400"
            >
              <FileCheck className="h-3 w-3" />
              Ready
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 pb-3">
        {match.location && (
          <div className="mb-2 flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3" />
            {match.location}
          </div>
        )}
        <p className="line-clamp-3 text-sm text-muted-foreground">
          {match.reason}
        </p>
      </CardContent>
      <CardFooter className="flex items-center justify-between border-t pt-3">
        <span className="text-xs text-muted-foreground">
          {formatDistanceToNow(new Date(match.createdAt), { addSuffix: true })}
        </span>
        <Button asChild size="sm" variant="ghost" className="gap-1 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
          <Link href={`/dashboard/matches/${match.id}`}>
            View Details
            <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
