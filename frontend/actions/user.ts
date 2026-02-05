"use server";

import { auth } from "@/lib/auth";
import prisma from "@/lib/prisma";
import { headers } from "next/headers";

export interface OnboardingProfile {
  profile_text: string | null;
  location: string | null;
  name: string;
  email: string;
  source_pdfs: string[] | null;
  references: Record<string, unknown> | null;
  suggested_job_titles: string[] | null;
}

/**
 * Get the current user's profile for the onboarding agent (chat) step.
 * Uses the session user id; assumes backend profiling has already written
 * to the same user row (by name+email).
 */
export async function getOnboardingProfile(): Promise<OnboardingProfile | null> {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return null;
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      profile_text: true,
      location: true,
      name: true,
      email: true,
      source_pdfs: true,
      references: true,
      suggested_job_titles: true,
    },
  });

  if (!user) {
    return null;
  }

  // Handle source_pdfs: can be array of strings or object with keys
  let source_pdfs: string[] | null = null;
  if (user.source_pdfs) {
    if (Array.isArray(user.source_pdfs)) {
      source_pdfs = user.source_pdfs;
    } else if (typeof user.source_pdfs === "object") {
      // If it's an object, extract values (URLs)
      source_pdfs = Object.values(user.source_pdfs).filter(
        (v): v is string => typeof v === "string"
      );
    }
  }

  const references = user.references as Record<string, unknown> | null;
  const suggested_job_titles = user.suggested_job_titles as string[] | null;

  return {
    profile_text: user.profile_text,
    location: user.location,
    name: user.name,
    email: user.email,
    source_pdfs,
    references: references && typeof references === "object" ? references : null,
    suggested_job_titles: Array.isArray(suggested_job_titles)
      ? suggested_job_titles
      : null,
  };
}

/**
 * Check if the current user has completed onboarding (has profile_text).
 * Used by the redirect page to determine if user needs onboarding.
 */
export async function hasUserProfile(): Promise<boolean> {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return false;
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      profile_text: true,
    },
  });

  // User has profile if profile_text exists and is not empty
  return !!user?.profile_text;
}

export interface UserWithProfile {
  id: string;
  name: string;
  email: string;
  location: string | null;
  profile_text: string | null;
  suggested_job_titles: string[] | null;
  source_pdfs: string[] | null;
  hasAccess: boolean;
}

/**
 * Get the current user with full profile data.
 * Used by the job search page to get user ID and profile information.
 */
export async function getCurrentUserWithProfile(): Promise<UserWithProfile | null> {
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session?.user?.id) {
    return null;
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      id: true,
      name: true,
      email: true,
      location: true,
      profile_text: true,
      suggested_job_titles: true,
      source_pdfs: true,
      hasAccess: true,
    },
  });

  if (!user) {
    return null;
  }

  // Handle source_pdfs: can be array of strings or object with keys
  let source_pdfs: string[] | null = null;
  if (user.source_pdfs) {
    if (Array.isArray(user.source_pdfs)) {
      source_pdfs = user.source_pdfs;
    } else if (typeof user.source_pdfs === "object") {
      source_pdfs = Object.values(user.source_pdfs).filter(
        (v): v is string => typeof v === "string"
      );
    }
  }

  const suggested_job_titles = user.suggested_job_titles as string[] | null;

  return {
    id: user.id,
    name: user.name,
    email: user.email,
    location: user.location,
    profile_text: user.profile_text,
    suggested_job_titles: Array.isArray(suggested_job_titles)
      ? suggested_job_titles
      : null,
    source_pdfs,
    hasAccess: user.hasAccess,
  };
}
