"use client";

// settings page — profile, notifications, pipeline status, account deletion
// wired to backend PATCH /auth/profile, PATCH /auth/notifications, DELETE /auth/account

import { useMemo, useState } from "react";
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
import {
  updateProfile,
  updateNotifications,
  deleteAccount,
  ApiError,
} from "@/lib/api";
import type { Therapist } from "@/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const therapist = user as Therapist | null;

  const [name, setName] = useState(therapist?.name ?? "");
  const [email] = useState(therapist?.email ?? "");
  const [specialization, setSpecialization] = useState(
    therapist?.specialization ?? ""
  );
  const [practiceName, setPracticeName] = useState(
    therapist?.practiceName ?? ""
  );

  const [notifyPipeline, setNotifyPipeline] = useState(true);
  const [notifyWeeklyDigest, setNotifyWeeklyDigest] = useState(false);
  const [notifyRagCitations, setNotifyRagCitations] = useState(true);

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingNotifs, setSavingNotifs] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const canDelete = useMemo(() => deleteConfirm === "DELETE", [deleteConfirm]);

  const handleSaveProfile = async () => {
    if (!name.trim()) {
      setErrorMessage("name is required.");
      setStatusMessage(null);
      return;
    }
    setSaving(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      await updateProfile({
        name: name.trim(),
        specialization: specialization.trim() || undefined,
        practiceName: practiceName.trim() || undefined,
      });
      setStatusMessage("profile changes saved successfully.");
    } catch (err: unknown) {
      setErrorMessage((err as ApiError)?.detail || "failed to save profile changes.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotifications = async () => {
    setSavingNotifs(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      await updateNotifications({
        emailNotifications: notifyPipeline,
        journalAlerts: notifyRagCitations,
        weeklyDigest: notifyWeeklyDigest,
      });
      setStatusMessage("notification preferences updated.");
    } catch (err: unknown) {
      setErrorMessage((err as ApiError)?.detail || "failed to save notification preferences.");
    } finally {
      setSavingNotifs(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!canDelete) {
      setErrorMessage('type "DELETE" to confirm account deletion.');
      setStatusMessage(null);
      return;
    }

    setDeleting(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      await deleteAccount();
      setStatusMessage("account deleted. signing out...");
      setTimeout(() => logout(), 350);
    } catch (err: unknown) {
      setErrorMessage((err as ApiError)?.detail || "failed to delete account.");
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Manage your account and practice settings
        </p>
      </div>

      {statusMessage && (
        <div className="rounded-lg border bg-muted/40 px-3 py-2">
          <p className="text-sm font-medium">Settings updated</p>
          <p className="text-xs text-muted-foreground">{statusMessage}</p>
        </div>
      )}
      {errorMessage && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
          <p className="text-sm font-medium text-destructive">Action needed</p>
          <p className="text-xs text-destructive/90">{errorMessage}</p>
        </div>
      )}

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
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={email} disabled />
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
              <Input id="specialization" value={specialization} onChange={(e) => setSpecialization(e.target.value)} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="practice">Practice name</Label>
            <Input id="practice" value={practiceName} onChange={(e) => setPracticeName(e.target.value)} />
          </div>
          <Button onClick={handleSaveProfile} disabled={saving}>
            {saving ? "Saving..." : "Save changes"}
          </Button>
        </CardContent>
      </Card>

      {/* notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Notification Preferences</CardTitle>
          <CardDescription>
            Configure which operational updates you receive
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Pipeline run status</p>
              <p className="text-xs text-muted-foreground">
                Receive success/failure alerts for data pipelines
              </p>
            </div>
            <Switch checked={notifyPipeline} onCheckedChange={setNotifyPipeline} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Weekly summary digest</p>
              <p className="text-xs text-muted-foreground">
                Get a weekly overview of patient activity trends
              </p>
            </div>
            <Switch checked={notifyWeeklyDigest} onCheckedChange={setNotifyWeeklyDigest} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">RAG citation reminders</p>
              <p className="text-xs text-muted-foreground">
                Remind when source citations are missing from responses
              </p>
            </div>
            <Switch checked={notifyRagCitations} onCheckedChange={setNotifyRagCitations} />
          </div>
          <Button variant="outline" onClick={handleSaveNotifications} disabled={savingNotifs}>
            {savingNotifs ? "Saving..." : "Save notification preferences"}
          </Button>
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
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete Account</p>
              <p className="text-xs text-muted-foreground">
                Permanently remove your account and all associated data
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={logout}>
              Sign out now
            </Button>
          </div>
          <div className="space-y-2">
            <Label htmlFor="delete-confirm" className="text-xs text-muted-foreground">
              Type DELETE to confirm
            </Label>
            <Input
              id="delete-confirm"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="DELETE"
            />
          </div>
          <div className="flex justify-end">
            <Button
              variant="destructive"
              size="sm"
              disabled={!canDelete || deleting}
              onClick={handleDeleteAccount}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
