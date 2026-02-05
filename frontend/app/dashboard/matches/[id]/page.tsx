import { headers } from "next/headers";
import { notFound } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { MatchDetailContent } from "@/components/dashboard/MatchDetailContent";
import { ArrowLeft, Home } from "lucide-react";

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

  const pdfUrl = cvData?.pdf_url || null;
  const coverLetterContent = formatCoverLetter(artifacts?.cover_letter as CoverLetterData | null);
  const applyUrl = applicationLink?.link || applicationLink?.url || job?.share_link || null;

  return (
    <div className="space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link href="/dashboard" className="flex items-center gap-1">
                  <Home className="h-3.5 w-3.5" />
                  Dashboard
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link href="/dashboard/matches">Matches</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="max-w-[200px] truncate">
                {job?.title || "Job Match"}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        
        <Button asChild variant="ghost" size="sm" className="gap-1.5">
          <Link href="/dashboard/matches">
            <ArrowLeft className="h-4 w-4" />
            Back to Matches
          </Link>
        </Button>
      </div>

      {/* Main Content with Tabs */}
      <MatchDetailContent
        job={job ? {
          title: job.title,
          company_name: job.company_name,
          location: job.location,
          description: job.description,
        } : null}
        match={{
          reason: match.reason,
          job_description_summary: match.job_description_summary,
        }}
        coverLetterContent={coverLetterContent}
        pdfUrl={pdfUrl}
        applyUrl={applyUrl}
      />
    </div>
  );
}
