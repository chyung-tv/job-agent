"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { authClient } from "@/lib/auth-client";
import { useOnboardingStore } from "@/store/useOnboardingStore";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const identityFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email address"),
  location: z.string().min(1, "Location is required"),
});

type IdentityFormValues = z.infer<typeof identityFormSchema>;

export default function IdentityPage() {
  const router = useRouter();
  const { name, email, location, setName, setEmail, setLocation } =
    useOnboardingStore();
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<IdentityFormValues>({
    resolver: zodResolver(identityFormSchema),
    defaultValues: {
      name: name || "",
      email: email || "",
      location: location || "",
    },
  });

  // Fetch session and pre-fill form
  useEffect(() => {
    async function loadSession() {
      try {
        const session = await authClient.getSession();
        if (session?.data?.user) {
          const userName = session.data.user.name || "";
          const userEmail = session.data.user.email || "";

          // Pre-fill form
          form.setValue("name", userName);
          form.setValue("email", userEmail);

          // Pre-fill store if not already set
          if (!name) setName(userName);
          if (!email) setEmail(userEmail);
        }
      } catch (error) {
        console.error("Failed to load session:", error);
      } finally {
        setIsLoading(false);
      }
    }

    loadSession();
  }, [form, name, email, setName, setEmail]);

  const onSubmit = async (values: IdentityFormValues) => {
    try {
      setIsSubmitting(true);

      // Save to store
      setName(values.name);
      setEmail(values.email);
      setLocation(values.location);

      // Navigate to uploads step
      router.push("/onboarding/uploads");
    } catch (error) {
      console.error("Failed to save identity:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="w-full">
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">Loading...</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-2xl font-bold">Identity Information</CardTitle>
        <CardDescription>
          Please verify your information and provide your location
        </CardDescription>
      </CardHeader>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      disabled
                      className="bg-muted"
                      placeholder="Your name"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      type="email"
                      disabled
                      className="bg-muted"
                      placeholder="your.email@example.com"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="location"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Location *</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      placeholder="e.g., San Francisco, CA"
                      disabled={isSubmitting}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
          <CardFooter className="flex justify-end">
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving..." : "Continue"}
            </Button>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}
