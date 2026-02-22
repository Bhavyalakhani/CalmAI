"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Brain, ArrowRight, Stethoscope, BookHeart } from "lucide-react";
import type { UserRole } from "@/types";

export default function SignupPage() {
  const router = useRouter();
  const [step, setStep] = useState<"role" | "form">("role");
  const [role, setRole] = useState<UserRole>("therapist");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    // simulate signup — replace with real api call
    await new Promise((r) => setTimeout(r, 1200));
    setIsLoading(false);
    router.push(role === "therapist" ? "/dashboard" : "/journal");
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      {/* Logo */}
      <Link
        href="/"
        className="mb-8 flex items-center gap-2 text-muted-foreground transition-colors hover:text-foreground"
      >
        <Brain className="h-6 w-6" />
        <span className="text-lg font-bold tracking-tight">CalmAI</span>
      </Link>

      {step === "role" ? (
        /* step 1: choose role */
        <div className="w-full max-w-lg space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight">
              Create your account
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Choose how you&apos;ll use CalmAI
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <RoleCard
              selected={role === "therapist"}
              onClick={() => setRole("therapist")}
              icon={<Stethoscope className="h-6 w-6" />}
              title="Therapist"
              description="Manage patients, review journals, access analytics & RAG search"
            />
            <RoleCard
              selected={role === "patient"}
              onClick={() => setRole("patient")}
              icon={<BookHeart className="h-6 w-6" />}
              title="Patient"
              description="Write journal entries, view insights, respond to prompts"
            />
          </div>

          <Button
            className="w-full"
            size="lg"
            onClick={() => setStep("form")}
          >
            Continue as {role === "therapist" ? "Therapist" : "Patient"}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-medium text-foreground underline underline-offset-4 hover:no-underline"
            >
              Log in
            </Link>
          </p>
        </div>
      ) : (
        /* step 2: registration form */
        <Card className="w-full max-w-md border bg-card">
          <CardHeader className="text-center">
            <CardTitle className="text-xl">
              {role === "therapist"
                ? "Therapist Registration"
                : "Patient Registration"}
            </CardTitle>
            <CardDescription>
              Fill in your details to get started
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">First name</Label>
                  <Input
                    id="firstName"
                    placeholder="Sarah"
                    required
                    autoFocus
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last name</Label>
                  <Input id="lastName" placeholder="Chen" required />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Min 8 characters"
                  required
                  minLength={8}
                />
              </div>

              {role === "therapist" && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <Label htmlFor="license">License number</Label>
                    <Input
                      id="license"
                      placeholder="PSY-2024-XXXXX"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="specialization">Specialization</Label>
                    <Input
                      id="specialization"
                      placeholder="e.g. Cognitive Behavioral Therapy"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="practice">
                      Practice name{" "}
                      <span className="text-muted-foreground">(optional)</span>
                    </Label>
                    <Input
                      id="practice"
                      placeholder="e.g. Mindful Path Clinic"
                    />
                  </div>
                </>
              )}

              {role === "patient" && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <Label htmlFor="therapistCode">
                      Therapist invite code
                    </Label>
                    <Input
                      id="therapistCode"
                      placeholder="Enter the code from your therapist"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="dob">Date of birth</Label>
                    <Input id="dob" type="date" required />
                  </div>
                </>
              )}

              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={isLoading}
              >
                {isLoading ? "Creating account..." : "Create account"}
              </Button>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground"
                  onClick={() => setStep("role")}
                >
                  &larr; Back
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* role card sub-component */

function RoleCard({
  selected,
  onClick,
  icon,
  title,
  description,
}: {
  selected: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-3 rounded-xl border-2 p-6 text-center transition-colors ${
        selected
          ? "border-foreground bg-muted"
          : "border-border hover:border-muted-foreground/50 hover:bg-muted/50"
      }`}
    >
      <div
        className={`flex h-12 w-12 items-center justify-center rounded-full ${
          selected ? "bg-foreground text-background" : "bg-muted"
        }`}
      >
        {icon}
      </div>
      <div>
        <div className="font-semibold">{title}</div>
        <div className="mt-1 text-xs text-muted-foreground">{description}</div>
      </div>
    </button>
  );
}
