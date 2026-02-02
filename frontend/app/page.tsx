import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12 dark:bg-gray-900">
      <main className="flex w-full max-w-2xl flex-col items-center gap-8 text-center">
        <div className="space-y-4">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-50">
            Welcome to Job Agent
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-400">
            Get started by signing up or signing in to your account.
          </p>
        </div>
        <div className="flex gap-4">
          <Button asChild>
            <Link href="/signup">Get Started</Link>
          </Button>
        </div>
      </main>
    </div>
  );
}
