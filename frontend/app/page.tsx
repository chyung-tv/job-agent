import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  FileText,
  Target,
  Zap,
  ArrowRight,
  CheckCircle2,
  Briefcase,
} from "lucide-react";

const features = [
  {
    icon: Target,
    title: "AI-Powered Matching",
    description:
      "Our intelligent system analyzes your profile and matches you with positions that fit your skills and aspirations.",
  },
  {
    icon: FileText,
    title: "Tailored CVs & Cover Letters",
    description:
      "Get custom-generated documents for each application, highlighting the most relevant experience for every role.",
  },
  {
    icon: Zap,
    title: "Automated Discovery",
    description:
      "Continuously discover new opportunities across multiple job boards without manual searching.",
  },
];

const benefits = [
  "Save hours on job applications",
  "Stand out with personalized materials",
  "Never miss a perfect opportunity",
  "Track all your applications in one place",
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Hero Section */}
      <section className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-linear-to-b from-background via-background to-muted/30 px-4 py-20 md:py-32">
        {/* Background decoration */}
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(45%_40%_at_50%_60%,hsl(var(--primary)/0.08)_0%,transparent_100%)]" />
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_80%_20%,hsl(var(--primary)/0.05)_0%,transparent_50%)]" />
        
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-8 text-center">
          <Badge variant="secondary" className="gap-1.5 px-3 py-1">
            <Sparkles className="h-3.5 w-3.5" />
            AI-Powered Job Search
          </Badge>
          
          <div className="space-y-4">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
              Your Personal
              <span className="bg-linear-to-r from-primary/80 to-primary bg-clip-text text-transparent">
                {" "}AI Job Agent
              </span>
            </h1>
            <p className="mx-auto max-w-2xl text-lg text-muted-foreground md:text-xl">
              Upload your CV once and let AI find, match, and apply to jobs that fit your
              career goals. Get tailored applications that stand out.
            </p>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row">
            <Button asChild size="lg" className="gap-2">
              <Link href="/signup">
                Get Started Free
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/sign-in">Sign In</Link>
            </Button>
          </div>

          {/* Quick benefits */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            {benefits.slice(0, 3).map((benefit, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span>{benefit}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="border-t bg-muted/30 px-4 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-bold tracking-tight">
              How It Works
            </h2>
            <p className="mx-auto max-w-2xl text-muted-foreground">
              Transform your job search with intelligent automation and personalized
              application materials.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {features.map((feature, index) => (
              <Card
                key={index}
                className="group relative overflow-hidden border-border/50 bg-card/50 backdrop-blur-sm transition-all duration-300 hover:border-primary/20 hover:shadow-lg hover:shadow-primary/5"
              >
                <CardHeader>
                  <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                    <feature.icon className="h-6 w-6" />
                  </div>
                  <CardTitle className="text-xl">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t px-4 py-20">
        <div className="mx-auto max-w-4xl text-center">
          <div className="rounded-2xl border bg-linear-to-br from-card via-card to-muted/50 p-8 shadow-lg md:p-12">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <Briefcase className="h-8 w-8 text-primary" />
            </div>
            <h2 className="mb-4 text-2xl font-bold tracking-tight md:text-3xl">
              Ready to Transform Your Job Search?
            </h2>
            <p className="mx-auto mb-8 max-w-xl text-muted-foreground">
              Join thousands of professionals who&apos;ve accelerated their career
              journey with AI-powered job matching.
            </p>
            <Button asChild size="lg" className="gap-2">
              <Link href="/signup">
                Start Your Free Trial
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-muted/30 px-4 py-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Briefcase className="h-4 w-4" />
            <span>Job Agent</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Built with AI to help you succeed
          </p>
        </div>
      </footer>
    </div>
  );
}
