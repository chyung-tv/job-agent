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
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <CardTitle className="line-clamp-2 text-base">
              {match.title}
            </CardTitle>
            <CardDescription className="flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {match.company}
            </CardDescription>
          </div>
          {match.hasArtifacts && (
            <div className="flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700 dark:bg-green-900 dark:text-green-300">
              <FileCheck className="h-3 w-3" />
              Ready
            </div>
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
        <Button asChild size="sm" variant="ghost">
          <Link href={`/dashboard/matches/${match.id}`}>
            View Details
            <ArrowRight className="ml-1 h-3 w-3" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
