"use client";

import { triggerProfiling } from "@/actions/workflow";
import { generateProfileQuestions } from "@/actions/agent";
import { getOnboardingProfile } from "@/actions/user";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/store/useOnboardingStore";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type QuestionAnswer = { question: string; answer: string };

function aggregateQAPairs(pairs: QuestionAnswer[]): string {
  return pairs
    .filter((p) => p.answer.trim())
    .map((p) => `Q: ${p.question}\nA: ${p.answer.trim()}`)
    .join("\n\n");
}

export default function ChatPage() {
  const router = useRouter();
  const { name, email, location, cv_files } = useOnboardingStore();

  const [profile, setProfile] = useState<Awaited<ReturnType<typeof getOnboardingProfile>>>(null);
  const [questions, setQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState<"profile" | "questions" | "idle" | "submit">("profile");
  const [error, setError] = useState<string | null>(null);

  const [startedChat, setStartedChat] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<QuestionAnswer[]>([]);
  const [currentAnswer, setCurrentAnswer] = useState("");

  const loadProfileAndQuestions = useCallback(async () => {
    setLoading("profile");
    setError(null);
    try {
      const p = await getOnboardingProfile();
      setProfile(p);
      if (!p?.profile_text?.trim()) {
        setLoading("idle");
        return;
      }
      setLoading("questions");
      const result = await generateProfileQuestions(p.profile_text);
      if (result?.questions?.length) {
        setQuestions(result.questions);
        setAnswers(result.questions.map((q) => ({ question: q, answer: "" })));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load profile");
    } finally {
      setLoading("idle");
    }
  }, []);

  useEffect(() => {
    loadProfileAndQuestions();
  }, [loadProfileAndQuestions]);

  // Determine if we're coming from onboarding flow (store has data) or dashboard (store empty)
  const isFromOnboarding = cv_files.length > 0;

  const handleContinueWithoutChat = () => {
    // If coming from dashboard, go back to dashboard profile
    router.push(isFromOnboarding ? "/onboarding/profile" : "/dashboard/profile");
  };

  const handleStartChat = () => {
    setStartedChat(true);
    setCurrentIndex(0);
    setCurrentAnswer(answers[0]?.answer ?? "");
  };

  const handleNext = () => {
    const nextAnswers = [...answers];
    nextAnswers[currentIndex] = {
      ...nextAnswers[currentIndex],
      answer: currentAnswer.trim(),
    };
    setAnswers(nextAnswers);
    setCurrentAnswer(nextAnswers[currentIndex + 1]?.answer ?? "");
    setCurrentIndex((i) => Math.min(i + 1, questions.length - 1));
  };

  const handleBack = () => {
    const nextIndex = Math.max(0, currentIndex - 1);
    const nextAnswers = [...answers];
    nextAnswers[currentIndex] = {
      ...nextAnswers[currentIndex],
      answer: currentAnswer.trim(),
    };
    setAnswers(nextAnswers);
    setCurrentIndex(nextIndex);
    setCurrentAnswer(nextAnswers[nextIndex]?.answer ?? "");
  };

  const handleFinishAndContinue = async () => {
    const finalAnswers = [...answers];
    finalAnswers[currentIndex] = {
      ...finalAnswers[currentIndex],
      answer: currentAnswer.trim(),
    };
    const basicInfo = aggregateQAPairs(finalAnswers);
    if (!basicInfo.trim()) {
      router.push(isFromOnboarding ? "/onboarding/profile" : "/dashboard/profile");
      return;
    }

    // Use store data if available, otherwise fall back to profile from DB
    const userName = name || profile?.name;
    const userEmail = email || profile?.email;
    const userLocation = location || profile?.location;
    const cvUrls = cv_files.length > 0
      ? cv_files.map((f) => f.url)
      : profile?.source_pdfs || [];

    if (!userName || !userEmail || !userLocation || cvUrls.length === 0) {
      setError("Missing profile data. Please complete onboarding first.");
      return;
    }

    setLoading("submit");
    setError(null);
    try {
      console.log(
        "[Second profiling] Firing with basic_info length:",
        basicInfo.length,
        "preview:",
        basicInfo.slice(0, 200)
      );
      const response = await triggerProfiling({
        name: userName,
        email: userEmail,
        location: userLocation,
        cv_urls: cvUrls,
        basic_info: basicInfo,
      });
      console.log(
        "[Second profiling] Backend accepted, run_id:",
        response.run_id,
        "task_id:",
        response.task_id
      );
      
      // Determine redirect based on source (store has data = onboarding flow)
      const nextUrl = isFromOnboarding
        ? `/onboarding/processing?run_id=${response.run_id}&next=/onboarding/profile`
        : `/onboarding/processing?run_id=${response.run_id}&next=/dashboard/profile`;
      
      router.push(nextUrl);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update profile");
      setLoading("idle");
    }
  };

  if (loading === "profile" || loading === "questions") {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Preparing your chat</CardTitle>
          <CardDescription>
            {loading === "profile"
              ? "Loading your profile..."
              : "Generating questions..."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (error && !profile) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Something went wrong</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardFooter>
          <Button variant="outline" onClick={loadProfileAndQuestions}>
            Retry
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (!profile?.profile_text?.trim() || questions.length === 0) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Profile not ready yet</CardTitle>
          <CardDescription>
            Your profile is still being prepared. You can continue without
            chatting and view your profile once it’s ready.
          </CardDescription>
        </CardHeader>
        <CardFooter>
          <Button onClick={handleContinueWithoutChat}>
            Continue without chatting
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (!startedChat) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Quick chat (optional)</CardTitle>
          <CardDescription>
            Answer a few short questions so we can refine your profile. You can
            skip this step and go straight to your profile.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </CardContent>
        <CardFooter className="flex gap-2">
          <Button onClick={handleContinueWithoutChat} variant="outline">
            Continue without chatting
          </Button>
          <Button onClick={handleStartChat}>Start chat</Button>
        </CardFooter>
      </Card>
    );
  }

  const isLast = currentIndex >= questions.length - 1;
  const currentQ = questions[currentIndex];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Question {currentIndex + 1} of {questions.length}</CardTitle>
        <CardDescription>{currentQ}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="answer">Your answer</Label>
          <Input
            id="answer"
            value={currentAnswer}
            onChange={(e) => setCurrentAnswer(e.target.value)}
            placeholder="Type your answer..."
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentIndex === 0}
        >
          Back
        </Button>
        {isLast ? (
          <Button
            onClick={handleFinishAndContinue}
            disabled={loading === "submit"}
          >
            {loading === "submit" ? "Submitting..." : "Continue"}
          </Button>
        ) : (
          <Button onClick={handleNext}>Next</Button>
        )}
      </CardFooter>
    </Card>
  );
}
