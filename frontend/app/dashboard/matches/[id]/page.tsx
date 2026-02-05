import { headers } from "next/headers";
import { notFound } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { CoverLetterView } from "@/components/dashboard/CoverLetterView";
import { ApplyButton } from "@/components/dashboard/ApplyButton";
import {
  Building2,
  MapPin,
  ArrowLeft,
  ExternalLink,
  FileText,
  Mail,
} from "lucide-react";

// Type definitions for cover letter structure
interface CoverLetterContent {
  subject_line?: string;
  salutation?: string;
  opening_paragraph?: string;
  body_paragraphs?: string[];
  closing_paragraph?: string;
  signature?: string;
}

interface CoverLetterData {
  content?: CoverLetterContent | string;
  text?: string;
}

/**
 * Format a structured cover letter object into a readable string.
 * Handles both legacy string format and new structured format.
 */
function formatCoverLetter(data: CoverLetterData | null): string | null {
  if (!data) return null;

  // Handle legacy string format
  if (typeof data.content === "string") return data.content;
  if (data.text) return data.text;

  // Handle structured format
  const content = data.content as CoverLetterContent;
  if (!content || typeof content !== "object") return null;

  const parts: string[] = [];
  if (content.salutation) parts.push(content.salutation);
  if (content.opening_paragraph) parts.push(content.opening_paragraph);
  if (content.body_paragraphs?.length) {
    parts.push(content.body_paragraphs.join("\n\n"));
  }
  if (content.closing_paragraph) parts.push(content.closing_paragraph);
  if (content.signature) parts.push(content.signature);

  return parts.length > 0 ? parts.join("\n\n") : null;
}

interface MatchDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function MatchDetailPage({ params }: MatchDetailPageProps) {
  const { id } = await params;
  
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return null;
  }

  // Fetch the matched job with all related data
  const match = await prisma.matched_jobs.findUnique({
    where: { id },
    include: {
      job_postings: true,
      artifacts: true,
    },
  });

  // Return 404 if not found or doesn't belong to user
  if (!match || match.user_id !== session.user.id) {
    notFound();
  }

  const job = match.job_postings;
  const artifacts = match.artifacts;

  // Parse artifact data
  const cvData = artifacts?.cv as { pdf_url?: string } | null;
  const applicationLink = match.application_link as { link?: string; url?: string } | null;

  const pdfUrl = cvData?.pdf_url;
  const coverLetterContent = formatCoverLetter(artifacts?.cover_letter as CoverLetterData | null);
  const applyUrl = applicationLink?.link || applicationLink?.url || job?.share_link;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button asChild variant="ghost" size="icon">
          <Link href="/dashboard/matches">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {job?.title || "Job Match"}
          </h1>
          <div className="flex items-center gap-4 text-muted-foreground">
            {job?.company_name && (
              <span className="flex items-center gap-1">
                <Building2 className="h-4 w-4" />
                {job.company_name}
              </span>
            )}
            {job?.location && (
              <span className="flex items-center gap-1">
                <MapPin className="h-4 w-4" />
                {job.location}
              </span>
            )}
          </div>
        </div>
        {applyUrl && <ApplyButton url={applyUrl} />}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Match Reason */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Why You Match</CardTitle>
            <CardDescription>
              AI analysis of why this position is a good fit for you.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{match.reason}</p>
            {match.job_description_summary && (
              <>
                <Separator className="my-4" />
                <div>
                  <h4 className="mb-2 text-sm font-medium">Job Summary</h4>
                  <p className="text-sm text-muted-foreground">
                    {match.job_description_summary}
                  </p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Cover Letter */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Mail className="h-5 w-5" />
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
              <p className="text-sm text-muted-foreground">
                Cover letter not yet generated.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Tailored CV */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              <div>
                <CardTitle className="text-lg">Tailored CV</CardTitle>
                <CardDescription>
                  Your CV customized for this specific position.
                </CardDescription>
              </div>
            </div>
            {pdfUrl ? (
              <Button asChild size="sm">
                <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Open CV
                </a>
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">
                Not yet generated
              </p>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Job Details */}
      {job?.description && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Full Job Description</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <pre className="whitespace-pre-wrap font-sans text-sm text-muted-foreground">
                {job.description}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
