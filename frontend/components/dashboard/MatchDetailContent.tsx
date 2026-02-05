"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { CoverLetterView } from "./CoverLetterView";
import { ApplyButton } from "./ApplyButton";
import {
  Building2,
  MapPin,
  ExternalLink,
  FileText,
  Mail,
  Sparkles,
  Briefcase,
  CheckCircle2,
} from "lucide-react";

interface MatchDetailContentProps {
  job: {
    title: string | null;
    company_name: string | null;
    location: string | null;
    description: string | null;
  } | null;
  match: {
    reason: string;
    job_description_summary: string | null;
  };
  coverLetterContent: string | null;
  pdfUrl: string | null;
  applyUrl: string | null;
}

export function MatchDetailContent({
  job,
  match,
  coverLetterContent,
  pdfUrl,
  applyUrl,
}: MatchDetailContentProps) {
  return (
    <div className="space-y-6">
      {/* Job Info Card */}
      <Card className="overflow-hidden border-primary/10 bg-linear-to-br from-card via-card to-muted/30">
        <CardHeader className="pb-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Briefcase className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-xl">
                    {job?.title || "Job Match"}
                  </CardTitle>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    {job?.company_name && (
                      <span className="flex items-center gap-1">
                        <Building2 className="h-3.5 w-3.5" />
                        {job.company_name}
                      </span>
                    )}
                    {job?.location && (
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3.5 w-3.5" />
                        {job.location}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
            {applyUrl && <ApplyButton url={applyUrl} />}
          </div>
        </CardHeader>
      </Card>

      {/* Tabbed Content */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="gap-1.5">
            <Sparkles className="h-4 w-4" />
            <span className="hidden sm:inline">Overview</span>
          </TabsTrigger>
          <TabsTrigger value="cover-letter" className="gap-1.5">
            <Mail className="h-4 w-4" />
            <span className="hidden sm:inline">Cover Letter</span>
          </TabsTrigger>
          <TabsTrigger value="cv" className="gap-1.5">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">CV</span>
          </TabsTrigger>
          <TabsTrigger value="job-details" className="gap-1.5">
            <Briefcase className="h-4 w-4" />
            <span className="hidden sm:inline">Job Details</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">Why You Match</CardTitle>
              </div>
              <CardDescription>
                AI analysis of why this position is a good fit for you.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg bg-primary/5 p-4">
                <p className="text-sm leading-relaxed">{match.reason}</p>
              </div>
              {match.job_description_summary && (
                <div className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-medium">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    Job Summary
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {match.job_description_summary}
                  </p>
                </div>
              )}
              
              {/* Artifacts Status */}
              <div className="flex flex-wrap gap-2 pt-2">
                <Badge
                  variant="outline"
                  className={
                    coverLetterContent
                      ? "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400"
                      : "border-muted"
                  }
                >
                  <Mail className="mr-1 h-3 w-3" />
                  Cover Letter {coverLetterContent ? "Ready" : "Pending"}
                </Badge>
                <Badge
                  variant="outline"
                  className={
                    pdfUrl
                      ? "border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400"
                      : "border-muted"
                  }
                >
                  <FileText className="mr-1 h-3 w-3" />
                  CV {pdfUrl ? "Ready" : "Pending"}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cover-letter" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">Cover Letter</CardTitle>
              </div>
              <CardDescription>
                AI-generated cover letter tailored for this position.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {coverLetterContent ? (
                <CoverLetterView content={coverLetterContent} />
              ) : (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
                  <Mail className="h-10 w-10 text-muted-foreground/50" />
                  <p className="mt-4 text-sm text-muted-foreground">
                    Cover letter not yet generated.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    This will be available once processing completes.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cv" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  <div>
                    <CardTitle className="text-lg">Tailored CV</CardTitle>
                    <CardDescription>
                      Your CV customized for this specific position.
                    </CardDescription>
                  </div>
                </div>
                {pdfUrl && (
                  <Button asChild size="sm" className="gap-1.5">
                    <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="h-4 w-4" />
                      Open CV
                    </a>
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {pdfUrl ? (
                <div className="overflow-hidden rounded-lg border bg-muted/30">
                  <iframe
                    src={pdfUrl}
                    className="h-[600px] w-full"
                    title="Tailored CV"
                  />
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
                  <FileText className="h-10 w-10 text-muted-foreground/50" />
                  <p className="mt-4 text-sm text-muted-foreground">
                    Tailored CV not yet generated.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    This will be available once processing completes.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="job-details" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Briefcase className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">Full Job Description</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {job?.description ? (
                <ScrollArea className="h-[500px] rounded-lg border bg-muted/30 p-4">
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                      {job.description}
                    </div>
                  </div>
                </ScrollArea>
              ) : (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
                  <Briefcase className="h-10 w-10 text-muted-foreground/50" />
                  <p className="mt-4 text-sm text-muted-foreground">
                    Job description not available.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
