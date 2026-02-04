"use server";

import { generateText, Output } from "ai";
import { google } from "@ai-sdk/google";
import { z } from "zod";

const questionsSchema = z.object({
  questions: z
    .array(z.string().min(1, "Question must not be empty"))
    .min(4, "At least 4 questions required")
    .max(6, "At most 6 questions allowed"),
});

export type GenerateProfileQuestionsResult = z.infer<typeof questionsSchema>;

/**
 * Generate ~5 short questions from the user's profile text for the onboarding
 * agent chat. Uses Vercel AI SDK generateText with Output.object (structured output).
 */
export async function generateProfileQuestions(
  profileText: string
): Promise<GenerateProfileQuestionsResult | null> {
  if (!profileText?.trim()) {
    return null;
  }

  console.log("[generateProfileQuestions] input length:", profileText?.length, "preview:", profileText?.slice(0, 300));

  const { output } = await generateText({
    model: google("gemini-2.5-flash"),
    output: Output.object({
      name: "ProfileQuestions",
      description: "Exactly 5 short questions to understand the candidate better.",
      schema: questionsSchema,
    }),
    prompt: `You are a friendly career coach. Based on the following candidate profile (extracted from their CV), generate exactly 5 short, open-ended questions to better understand their preferences, goals, and work style. Each question should be one sentence. Focus on: career goals, work environment preferences, key strengths they want to highlight, and what they're looking for in their next role.

Candidate profile:
${profileText.trim()}

Return only the list of 5 questions, no other text.`,
  });

  if (!output || !Array.isArray(output.questions)) {
    return null;
  }

  console.log("[generateProfileQuestions] result:", output?.questions);
  return { questions: output.questions };
}
