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
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/lib/auth-context";
import type { Therapist } from "@/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const therapist = user as Therapist | null;

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Manage your account and practice settings
        </p>
      </div>

      {/* profile */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Profile</CardTitle>
          <CardDescription>Your therapist profile information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" defaultValue={therapist?.name ?? ""} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" defaultValue={therapist?.email ?? ""} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="license">License number</Label>
              <Input
                id="license"
                defaultValue={therapist?.licenseNumber ?? ""}
                disabled
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="specialization">Specialization</Label>
              <Input
                id="specialization"
                defaultValue={therapist?.specialization ?? ""}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="practice">Practice name</Label>
            <Input
              id="practice"
              defaultValue={therapist?.practiceName ?? ""}
            />
          </div>
          <Button>Save changes</Button>
        </CardContent>
      </Card>

      {/* pipeline status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Pipeline Status</CardTitle>
          <CardDescription>
            Data pipeline and embedding configuration
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Embedding Model</p>
              <p className="text-xs text-muted-foreground">
                sentence-transformers/all-MiniLM-L6-v2
              </p>
            </div>
            <Badge variant="outline">384 dims</Badge>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Vector Store</p>
              <p className="text-xs text-muted-foreground">
                MongoDB Atlas - rag_vectors collection
              </p>
            </div>
            <Badge variant="secondary">Connected</Badge>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">
                Incoming Journals Pipeline
              </p>
              <p className="text-xs text-muted-foreground">
                Runs every 30 minutes via Airflow DAG
              </p>
            </div>
            <Badge variant="secondary">Active</Badge>
          </div>
        </CardContent>
      </Card>

      {/* danger zone */}
      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle className="text-sm text-destructive">
            Danger Zone
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete Account</p>
              <p className="text-xs text-muted-foreground">
                Permanently remove your account and all associated data
              </p>
            </div>
            <Button variant="destructive" size="sm">
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
