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
    },
  });

  if (!user) {
    return null;
  }

  const source_pdfs = user.source_pdfs as string[] | null;
  const references = user.references as Record<string, unknown> | null;

  return {
    profile_text: user.profile_text,
    location: user.location,
    name: user.name,
    email: user.email,
    source_pdfs: Array.isArray(source_pdfs) ? source_pdfs : null,
    references: references && typeof references === "object" ? references : null,
  };
}
