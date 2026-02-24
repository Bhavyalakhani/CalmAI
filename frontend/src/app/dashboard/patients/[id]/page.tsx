// patient profile page - therapist view of a single patient
// shows patient info, analytics, full journal timeline with filters, and prompts

"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  Calendar,
  Mail,
  BookOpen,
  Activity,
  Search,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Send,
  Loader2,
  Plus,
  UserX,
} from "lucide-react";
import {
  fetchPatient,
  fetchAnalytics,
  fetchJournals,
  fetchMoodTrend,
  fetchAllPrompts,
  createPrompt,
  removePatient,
} from "@/lib/api";
import type {
  Patient,
  PatientAnalytics,
  JournalEntry,
  TrendDataPoint,
  TherapistPrompt,
} from "@/types";

const PAGE_SIZE = 20;

export default function PatientProfilePage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.id as string;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [analytics, setAnalytics] = useState<PatientAnalytics | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [moodTrend, setMoodTrend] = useState<TrendDataPoint[]>([]);
  const [prompts, setPrompts] = useState<TherapistPrompt[]>([]);
  const [loading, setLoading] = useState(true);

  // prompt dialog
  const [promptDialogOpen, setPromptDialogOpen] = useState(false);
  const [newPromptText, setNewPromptText] = useState("");
  const [sendingPrompt, setSendingPrompt] = useState(false);

  // remove patient dialog
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState("");

  // filters
  const [searchQuery, setSearchQuery] = useState("");
  const [themeFilter, setThemeFilter] = useState("all");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [page, setPage] = useState(0);
  const [allJournals, setAllJournals] = useState<JournalEntry[]>([]);

  // load patient data
  useEffect(() => {
    if (!patientId) return;

    const loadData = async () => {
      try {
        const [patientData, analyticsData, journalData, moodData, promptData] =
          await Promise.all([
            fetchPatient(patientId),
            fetchAnalytics(patientId).catch(() => null),
            fetchJournals({ patientId, limit: 200 }),
            fetchMoodTrend(patientId, 30).catch(() => []),
            fetchAllPrompts(patientId).catch(() => []),
          ]);
        setPatient(patientData);
        setAnalytics(analyticsData);
        setAllJournals(journalData);
        setMoodTrend(moodData);
        setPrompts(promptData);
      } catch (err) {
        console.error("failed to load patient profile:", err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [patientId]);

  // apply filters and pagination
  useEffect(() => {
    let filtered = [...allJournals];

    // text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter((j) => j.content.toLowerCase().includes(q));
    }

    // theme filter
    if (themeFilter !== "all") {
      filtered = filtered.filter((j) =>
        j.themes.includes(themeFilter)
      );
    }

    // sort
    filtered.sort((a, b) => {
      const dateA = new Date(a.entryDate).getTime();
      const dateB = new Date(b.entryDate).getTime();
      return sortOrder === "desc" ? dateB - dateA : dateA - dateB;
    });

    setJournals(filtered);
    setPage(0);
  }, [allJournals, searchQuery, themeFilter, sortOrder]);

  const totalPages = Math.ceil(journals.length / PAGE_SIZE);
  const paginatedJournals = journals.slice(
    page * PAGE_SIZE,
    (page + 1) * PAGE_SIZE
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
          <Skeleton className="h-96" />
          <div className="space-y-4">
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
          </div>
        </div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <p className="text-muted-foreground">Patient not found</p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go back
        </Button>
      </div>
    );
  }

  const initials = patient.name
    .split(" ")
    .map((n) => n[0])
    .join("");

  const handleSendPrompt = async () => {
    if (!newPromptText.trim()) return;
    setSendingPrompt(true);
    try {
      const created = await createPrompt(patientId, newPromptText);
      setPrompts((prev) => [created, ...prev]);
      setNewPromptText("");
      setPromptDialogOpen(false);
    } catch (err) {
      console.error("failed to create prompt:", err);
    } finally {
      setSendingPrompt(false);
    }
  };

  const handleRemovePatient = async () => {
    setRemoveError("");
    setRemoving(true);
    try {
      await removePatient(patientId);
      router.push("/dashboard/patients");
    } catch {
      setRemoveError("Failed to remove patient. Please try again.");
    } finally {
      setRemoving(false);
    }
  };

  const pendingPrompts = prompts.filter((p) => p.status === "pending");

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-3">
            <Avatar className="h-10 w-10">
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <div>
              <h2 className="text-lg font-semibold">{patient.name}</h2>
              <p className="text-sm text-muted-foreground">{patient.email}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={promptDialogOpen} onOpenChange={setPromptDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <MessageSquare className="mr-2 h-4 w-4" />
                Assign Prompt
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Assign Reflection Prompt</DialogTitle>
                <DialogDescription>
                  Send a writing prompt to {patient.name}. They&apos;ll see it on
                  their journal page and can respond with a journal entry.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <Textarea
                  placeholder="e.g., This week, write about a moment where you felt proud of yourself..."
                  className="min-h-[120px] resize-none text-sm"
                  value={newPromptText}
                  onChange={(e) => setNewPromptText(e.target.value)}
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    {newPromptText.length}/2000 characters
                  </span>
                  <Button
                    size="sm"
                    onClick={handleSendPrompt}
                    disabled={newPromptText.trim().length < 5 || sendingPrompt}
                  >
                    {sendingPrompt ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    {sendingPrompt ? "Sending..." : "Send Prompt"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          <Dialog open={removeDialogOpen} onOpenChange={(open) => {
            setRemoveDialogOpen(open);
            if (!open) setRemoveError("");
          }}>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost" className="text-red-500 hover:text-red-400 hover:bg-red-500/10">
                <UserX className="mr-2 h-4 w-4" />
                Remove
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Remove Patient</DialogTitle>
                <DialogDescription>
                  This will permanently delete {patient.name}&apos;s account and
                  all their data including journals, analytics, and prompts.
                  This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                {removeError && (
                  <p className="text-sm text-red-500">{removeError}</p>
                )}
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setRemoveDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleRemovePatient}
                    disabled={removing}
                  >
                    {removing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Remove Patient
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* info row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Email</p>
              <p className="truncate text-sm font-medium">{patient.email}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Onboarded</p>
              <p className="text-sm font-medium">
                {new Date(patient.onboardedAt).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Processed Entries</p>
              <p className="text-sm font-medium">
                {analytics?.totalEntries ?? allJournals.length}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">Top Topic</p>
              <p className="text-sm font-medium capitalize">
                {analytics?.topicDistribution[0]?.label ?? "-"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* main content */}
      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        {/* journal entries */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Processed Entries
              </CardTitle>
              <CardDescription>
                {journals.length} processed entries
                {themeFilter !== "all" && ` matching "${themeFilter}"`}
                {searchQuery && ` containing "${searchQuery}"`}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* filters */}
              <div className="flex flex-wrap gap-3">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search journal content..."
                    className="pl-9"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <Select value={themeFilter} onValueChange={setThemeFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Topic" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All topics</SelectItem>
                    {(analytics?.topicDistribution ?? []).map((t) => (
                      <SelectItem key={t.topicId} value={t.label}>
                        <span className="capitalize">{t.label}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={sortOrder}
                  onValueChange={(v) => setSortOrder(v as "desc" | "asc")}
                >
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="desc">Newest first</SelectItem>
                    <SelectItem value="asc">Oldest first</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Separator />

              {/* entries list */}
              {paginatedJournals.length > 0 ? (
                <div className="space-y-4">
                  {paginatedJournals.map((entry) => (
                    <div
                      key={entry.id}
                      className="rounded-lg border p-4 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-muted-foreground">
                            {new Date(entry.entryDate).toLocaleDateString(
                              "en-US",
                              {
                                weekday: "short",
                                month: "short",
                                day: "numeric",
                                year: "numeric",
                              }
                            )}
                          </span>
                          {entry.mood && (
                            <Badge variant="outline" className="text-[10px]">
                              Mood: {entry.mood}/5
                            </Badge>
                          )}
                        </div>
                        <span className="text-[10px] text-muted-foreground">
                          {entry.wordCount} words
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed">
                        {entry.content}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {entry.themes.map((theme) => (
                          <Badge
                            key={theme}
                            variant="secondary"
                            className="text-[10px] capitalize cursor-pointer"
                            onClick={() => setThemeFilter(theme)}
                          >
                            {theme}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))}

                  {/* pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-2">
                      <p className="text-xs text-muted-foreground">
                        Page {page + 1} of {totalPages} ({journals.length}{" "}
                        processed entries)
                      </p>
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8"
                          disabled={page === 0}
                          onClick={() => setPage((p) => p - 1)}
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8"
                          disabled={page >= totalPages - 1}
                          onClick={() => setPage((p) => p + 1)}
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed p-12 text-center">
                  <p className="text-sm text-muted-foreground">
                    No processed entries found
                    {searchQuery && ` matching "${searchQuery}"`}
                    {themeFilter !== "all" && ` with theme "${themeFilter}"`}.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* sidebar: analytics */}
        <div className="space-y-4">
          {/* topic distribution */}
          {analytics && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  Topic Distribution
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {analytics.topicDistribution.map((t) => (
                  <div key={t.topicId} className="flex items-center gap-3">
                    <span className="w-32 shrink-0 text-xs capitalize text-muted-foreground break-words leading-tight" title={t.label}>
                      {t.label}
                    </span>
                    <div className="flex-1">
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-foreground/70"
                          style={{ width: `${t.percentage}%` }}
                        />
                      </div>
                    </div>
                    <span className="w-12 text-right text-xs font-medium">
                      {t.percentage}%
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* summary stats */}
          {analytics && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-lg font-bold">
                      {analytics.totalEntries}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Processed entries
                    </div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-lg font-bold">
                      {analytics.avgWordCount}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Avg. words
                    </div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-lg font-bold">
                      {analytics.dateRange?.spanDays ?? "-"}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Span (days)
                    </div>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <div className="text-lg font-bold capitalize">
                      {analytics.topicDistribution[0]?.label ?? "-"}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Top topic
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* monthly frequency */}
          {analytics && analytics.entryFrequency.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  Monthly Frequency
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-1">
                  {analytics.entryFrequency.map((ef) => {
                    const maxCount = Math.max(
                      ...analytics.entryFrequency.map((x) => x.count)
                    );
                    const heightPct = maxCount > 0 ? (ef.count / maxCount) * 100 : 0;
                    return (
                      <div key={ef.month} className="group relative flex-1">
                        <div
                          className="w-full rounded-sm bg-foreground/20 transition-colors group-hover:bg-foreground/40"
                          style={{
                            height: `${heightPct}%`,
                            minHeight: 4,
                            maxHeight: 48,
                          }}
                        />
                        <div className="mt-1 text-center text-[9px] text-muted-foreground">
                          {ef.month.slice(5)}
                        </div>
                        <div className="absolute -top-6 left-1/2 hidden -translate-x-1/2 rounded bg-foreground px-1.5 py-0.5 text-[10px] text-background group-hover:block">
                          {ef.count}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* mood trend */}
          {moodTrend.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  Mood Trend (30 days)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-1.5">
                  {moodTrend.map((point, i) => {
                    const height = (point.value / 5) * 100;
                    return (
                      <div key={i} className="group relative flex-1">
                        <div
                          className="w-full rounded-sm bg-foreground/20 transition-colors group-hover:bg-foreground/40"
                          style={{ height: `${height}%`, minHeight: 4 }}
                        />
                        <div className="absolute -top-8 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-foreground px-2 py-0.5 text-xs text-background group-hover:block">
                          {point.label} · {point.date.slice(5)}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
                  <span>{moodTrend[0]?.date.slice(5)}</span>
                  <span>{moodTrend[moodTrend.length - 1]?.date.slice(5)}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* prompts section */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  Assigned Prompts
                </CardTitle>
                <Badge variant="outline" className="text-[10px]">
                  {pendingPrompts.length} pending
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {prompts.length > 0 ? (
                <>
                  {prompts.slice(0, 5).map((prompt) => (
                    <div
                      key={prompt.promptId}
                      className="rounded-lg border p-3 space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={prompt.status === "pending" ? "outline" : "secondary"}
                          className="text-[10px]"
                        >
                          {prompt.status === "pending" ? "Pending" : "Answered"}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(prompt.createdAt).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {prompt.promptText}
                      </p>
                      {prompt.responseContent && (
                        <p className="text-xs text-muted-foreground/70 line-clamp-1 italic">
                          Response: {prompt.responseContent}
                        </p>
                      )}
                    </div>
                  ))}
                  {prompts.length > 5 && (
                    <p className="text-center text-[10px] text-muted-foreground">
                      +{prompts.length - 5} more prompts
                    </p>
                  )}
                </>
              ) : (
                <div className="rounded-lg border border-dashed p-4 text-center">
                  <p className="text-xs text-muted-foreground">
                    No prompts assigned yet
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 text-xs"
                    onClick={() => setPromptDialogOpen(true)}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    Assign first prompt
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
