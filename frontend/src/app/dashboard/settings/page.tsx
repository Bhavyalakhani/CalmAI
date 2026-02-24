"use client";

// settings page — profile, notifications, pipeline status, account deletion
// wired to backend PATCH /auth/profile, PATCH /auth/notifications, DELETE /auth/account

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Loader2, Trash2 } from "lucide-react";
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
  const router = useRouter();
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
  const [saving, setSaving] = useState(false);
  const [savingNotifs, setSavingNotifs] = useState(false);

  // delete account state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

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
    if (!canDelete) return;

    setDeleting(true);
    setDeleteError("");

    try {
      await deleteAccount();
      logout();
      router.push("/");
    } catch (err: unknown) {
      setDeleteError((err as ApiError)?.detail || "Failed to delete account. Please try again.");
    } finally {
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
      <Card className="border-red-900/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Trash2 className="h-4 w-4 text-red-500" />
            <CardTitle className="text-sm text-red-500">
              Danger Zone
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete Account</p>
              <p className="text-xs text-muted-foreground">
                Permanently remove your account, patients will be unlinked
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={logout}>
              Sign out now
            </Button>
          </div>
          <Separator />
          <p className="text-sm text-muted-foreground">
            This action is irreversible. Your account and all associated data
            will be permanently deleted. Your patients will be unlinked but
            their accounts will remain intact.
          </p>
          <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
            setDeleteDialogOpen(open);
            if (!open) {
              setDeleteConfirm("");
              setDeleteError("");
            }
          }}>
            <DialogTrigger asChild>
              <Button
                variant="destructive"
                size="sm"
                className="cursor-pointer transition-all hover:bg-red-600 hover:shadow-md hover:shadow-red-500/20"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Account
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Are you absolutely sure?</DialogTitle>
                <DialogDescription>
                  This will permanently delete your therapist account. Your
                  patients will be unlinked but their accounts will remain.
                  This cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="delete-confirm">
                    Type <span className="font-semibold text-red-500">DELETE</span> to confirm
                  </Label>
                  <Input
                    id="delete-confirm"
                    value={deleteConfirm}
                    onChange={(e) => setDeleteConfirm(e.target.value)}
                    placeholder="Type DELETE to confirm"
                  />
                </div>
                {deleteError && (
                  <p className="text-sm text-red-500">{deleteError}</p>
                )}
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDeleteDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDeleteAccount}
                    disabled={!canDelete || deleting}
                    className="cursor-pointer transition-all hover:bg-red-600"
                  >
                    {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Delete Forever
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </CardContent>
      </Card>
    </div>
  );
}
