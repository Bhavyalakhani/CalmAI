"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import type { Patient } from "@/types";

export default function JournalSettingsPage() {
  const { user, isLoading } = useAuth();
  const patient = user as Patient | null;

  if (isLoading || !patient) {
    return (
      <div className="max-w-2xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
        <Skeleton className="h-48" />
      </div>
    );
  }
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Manage your profile and preferences
        </p>
      </div>

      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Profile</CardTitle>
          <CardDescription>Your personal information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" defaultValue={patient.name} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" defaultValue={patient.email} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="dob">Date of birth</Label>
            <Input
              id="dob"
              type="date"
              defaultValue={patient.dateOfBirth ?? ""}
            />
          </div>
          <Button>Save changes</Button>
        </CardContent>
      </Card>

      {/* Therapist Link */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Your Therapist</CardTitle>
          <CardDescription>
            Currently linked to this therapist
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Dr. Sarah Chen</p>
              <p className="text-xs text-muted-foreground">
                Cognitive Behavioral Therapy · PSY-2024-11892
              </p>
            </div>
            <Badge variant="secondary">Active</Badge>
          </div>
          <Separator />
          <p className="text-xs text-muted-foreground">
            Your therapist can view your journal entries and analytics to provide
            better-informed care. They cannot edit your entries.
          </p>
        </CardContent>
      </Card>

      {/* Privacy */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Privacy</CardTitle>
          <CardDescription>
            Control who can see your data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-dashed p-4">
            <p className="text-sm text-muted-foreground">
              Your journal data is stored securely in MongoDB Atlas with
              encryption at rest. Only your assigned therapist can access your
              entries. CalmAI does not share data with third parties.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
