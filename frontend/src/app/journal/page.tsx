// patient journal page — write entries, view timeline, mood tracking
// supports prompt-aware submission via ?promptId= query param
// includes search, filter, pagination, edit/delete

"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BookOpen,
  Send,
  Clock,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  Search,
  Pencil,
  Trash2,
  X,
  Check,
  MessageSquare,
  CalendarDays,
  RefreshCw,
} from "lucide-react";
import {
  fetchJournals,
  fetchMoodTrend,
  fetchAnalytics,
  submitJournal,
  fetchPrompts,
  editJournal,
  deleteJournal,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type {
  JournalEntry,
  MoodScore,
  TrendDataPoint,
  Patient,
  PatientAnalytics,
  TherapistPrompt,
} from "@/types";

const PAGE_SIZE = 10;
const MAX_WORDS = 500;

// mood selector

const moodLabels: Record<MoodScore, { emoji: string; label: string }> = {
  1: { emoji: "😔", label: "Very Low" },
  2: { emoji: "😕", label: "Low" },
  3: { emoji: "😐", label: "Okay" },
  4: { emoji: "🙂", label: "Good" },
  5: { emoji: "😊", label: "Great" },
};

function MoodSelector({
  value,
  onChange,
}: {
  value: MoodScore | null;
  onChange: (mood: MoodScore) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">How are you feeling?</span>
      <div className="flex gap-1">
        {([1, 2, 3, 4, 5] as MoodScore[]).map((mood) => (
          <button
            key={mood}
            type="button"
            onClick={() => onChange(mood)}
            className={`flex h-9 w-9 items-center justify-center rounded-full border text-lg transition-colors ${
              value === mood
                ? "border-foreground bg-muted"
                : "border-transparent hover:bg-muted/50"
            }`}
            title={moodLabels[mood].label}
          >
            {moodLabels[mood].emoji}
          </button>
        ))}
      </div>
    </div>
  );
}

// journal entry card with edit/delete

function JournalEntryCard({
  entry,
  onEdit,
  onDelete,
}: {
  entry: JournalEntry;
  onEdit: (id: string, content: string) => void;
  onDelete: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(entry.content);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await editJournal(entry.id, { content: editContent });
      onEdit(entry.id, editContent);
      setEditing(false);
    } catch (err) {
      console.error("failed to edit journal:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteJournal(entry.id);
      onDelete(entry.id);
    } catch (err) {
      console.error("failed to delete journal:", err);
    }
  };

  return (
    <div className="group relative flex gap-4">
      {/* timeline dot & line */}
      <div className="flex flex-col items-center pt-1">
        <div className="h-2.5 w-2.5 rounded-full border-2 border-foreground bg-background" />
        <div className="flex-1 border-l border-dashed border-muted-foreground/30" />
      </div>

      {/* content */}
      <div className="flex-1 pb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">
              {new Date(entry.entryDate).toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
              })}
            </span>
            {entry.mood && (
              <span className="text-base" title={`Mood: ${entry.mood}/5`}>
                {moodLabels[entry.mood as MoodScore]?.emoji}
              </span>
            )}
            {entry.promptId && (
              <Badge variant="outline" className="text-[10px]">
                <MessageSquare className="mr-1 h-2.5 w-2.5" />
                Prompt response
              </Badge>
            )}
          </div>

          {/* edit/delete actions */}
          <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {!editing && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => { setEditing(true); setEditContent(entry.content); }}
                  title="Edit entry"
                >
                  <Pencil className="h-3 w-3" />
                </Button>
                {confirmDelete ? (
                  <div className="flex items-center gap-1">
                    <Button
                      variant="destructive"
                      size="icon"
                      className="h-7 w-7"
                      onClick={handleDelete}
                      title="Confirm delete"
                    >
                      <Check className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => setConfirmDelete(false)}
                      title="Cancel"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => setConfirmDelete(true)}
                    title="Delete entry"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        {editing ? (
          <div className="mt-2 space-y-2">
            <Textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="min-h-[80px] resize-none text-sm"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={saving || !editContent.trim()}>
                {saving ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Check className="mr-1 h-3 w-3" />}
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {entry.content}
          </p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {entry.themes.map((theme) => (
            <Badge
              key={theme}
              variant={theme === "processing" ? "outline" : "secondary"}
              className={`text-[10px] capitalize ${theme === "processing" ? "animate-pulse text-muted-foreground" : ""}`}
            >
              {theme === "processing" ? "Processing…" : theme}
            </Badge>
          ))}
          <span className="text-[10px] text-muted-foreground">
            {entry.wordCount} words
          </span>
          {entry.daysSinceLast !== null && (
            <span className="text-[10px] text-muted-foreground">
              · {entry.daysSinceLast}d since last
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// main page

export default function JournalPage() {
  const { user } = useAuth();
  const patient = user as Patient | null;
  const searchParams = useSearchParams();
  const router = useRouter();
  const promptIdParam = searchParams.get("promptId");

  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [moodTrend, setMoodTrend] = useState<TrendDataPoint[]>([]);
  const [analytics, setAnalytics] = useState<PatientAnalytics | null>(null);
  const [pendingPrompts, setPendingPrompts] = useState<TherapistPrompt[]>([]);
  const [activePrompt, setActivePrompt] = useState<TherapistPrompt | null>(null);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState("");
  const [mood, setMood] = useState<MoodScore | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  // search and filter
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const wordCount = content.trim().split(/\s+/).filter(Boolean).length;
  const overLimit = wordCount > MAX_WORDS;

  // filter journals by search and date range
  let filteredJournals = journals;
  if (searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filteredJournals = filteredJournals.filter((j) =>
      j.content.toLowerCase().includes(q)
    );
  }
  if (dateFrom) {
    filteredJournals = filteredJournals.filter(
      (j) => j.entryDate.slice(0, 10) >= dateFrom
    );
  }
  if (dateTo) {
    filteredJournals = filteredJournals.filter(
      (j) => j.entryDate.slice(0, 10) <= dateTo
    );
  }

  const totalPages = Math.ceil(filteredJournals.length / PAGE_SIZE);
  const displayedEntries = filteredJournals.slice(
    page * PAGE_SIZE,
    (page + 1) * PAGE_SIZE
  );

  const loadData = useCallback(async () => {
    if (!patient?.id) return;
    try {
      const [journalData, moodData, analyticsData, promptData] = await Promise.all([
        fetchJournals({ patientId: patient.id }),
        fetchMoodTrend(patient.id, 14).catch(() => []),
        fetchAnalytics(patient.id).catch(() => null),
        fetchPrompts(patient.id, "pending").catch(() => []),
      ]);
      setJournals(journalData);
      setMoodTrend(moodData);
      setAnalytics(analyticsData);
      setPendingPrompts(promptData);

      // if promptId in URL, find and set as active prompt
      if (promptIdParam && promptData.length > 0) {
        const target = promptData.find((p) => p.promptId === promptIdParam);
        if (target) setActivePrompt(target);
      }
    } catch (err) {
      console.error("failed to load journal data:", err);
    } finally {
      setLoading(false);
    }
  }, [patient?.id, promptIdParam]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // reset page on filter change
  useEffect(() => {
    setPage(0);
  }, [searchQuery, dateFrom, dateTo]);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setIsSubmitting(true);
    setSubmitMessage(null);

    try {
      await submitJournal(content, mood ?? undefined, activePrompt?.promptId);

      setContent("");
      setMood(null);
      setSubmitMessage("Entry saved successfully!");
      setActivePrompt(null);
      // auto-dismiss success message
      setTimeout(() => setSubmitMessage(null), 3000);
      // clear promptId from URL if present
      if (promptIdParam) {
        router.replace("/journal");
      }
      // refetch from server — new entry appears at top now that future dates are filtered
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save entry";
      setSubmitMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEdit = (id: string, newContent: string) => {
    setJournals((prev) =>
      prev.map((j) => (j.id === id ? { ...j, content: newContent } : j))
    );
    // refetch from server to sync stats
    loadData();
  };

  const handleDelete = (id: string) => {
    setJournals((prev) => prev.filter((j) => j.id !== id));
    // refetch from server to sync
    loadData();
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  if (loading) {
    return (
      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="space-y-8">
          <Skeleton className="h-64" />
          <Skeleton className="h-48" />
        </div>
        <div className="space-y-6">
          <Skeleton className="h-32" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      {/* main column */}
      <div className="space-y-8">
        {/* active prompt banner */}
        {activePrompt && (
          <Card className="border-foreground/20 bg-muted/50">
            <CardContent className="flex items-start gap-3 pt-6">
              <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1">
                <p className="text-xs font-medium text-muted-foreground">
                  Responding to prompt from {activePrompt.therapistName}
                </p>
                <p className="mt-1 text-sm italic">
                  &ldquo;{activePrompt.promptText}&rdquo;
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={() => {
                  setActivePrompt(null);
                  if (promptIdParam) router.replace("/journal");
                }}
              >
                <X className="h-3 w-3" />
              </Button>
            </CardContent>
          </Card>
        )}

        {/* new entry */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              <CardTitle className="text-sm font-medium">
                {activePrompt ? "Write Your Response" : "New Journal Entry"}
              </CardTitle>
            </div>
            <CardDescription>
              {activePrompt
                ? "Write a journal entry in response to your therapist's prompt."
                : "Write about your day, thoughts, or feelings. Your therapist can see your entries to provide better support."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="Start writing..."
              className="min-h-[160px] resize-none text-sm leading-relaxed"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />

            {submitMessage && (
              <p className={`text-sm ${submitMessage.includes("success") ? "text-emerald-500" : "text-destructive"}`}>
                {submitMessage}
              </p>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <MoodSelector value={mood} onChange={setMood} />
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs ${overLimit ? "font-medium text-destructive" : "text-muted-foreground"}`}>
                  {wordCount}/{MAX_WORDS} words
                </span>
                <Button
                  onClick={handleSubmit}
                  disabled={!content.trim() || !mood || overLimit || isSubmitting}
                  size="sm"
                  title={!mood ? "Select a mood first" : overLimit ? "Over word limit" : ""}
                >
                  {isSubmitting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  {isSubmitting ? "Saving..." : "Save Entry"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* timeline */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-medium">Your Journal Timeline</h2>
              <Badge variant="outline" className="text-[10px]">
                {journals.length} entries
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleRefresh}
              disabled={refreshing}
              title="Refresh"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </Button>
          </div>

          {/* filters */}
          {journals.length > 0 && (
            <div className="space-y-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search entries..."
                  className="pl-9 text-sm"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <CalendarDays className="h-4 w-4 text-muted-foreground" />
                <Input
                  type="date"
                  className="w-[140px] text-xs"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  placeholder="From"
                />
                <span className="text-xs text-muted-foreground">to</span>
                <Input
                  type="date"
                  className="w-[140px] text-xs"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  placeholder="To"
                />
                {(dateFrom || dateTo) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => { setDateFrom(""); setDateTo(""); }}
                  >
                    <X className="mr-1 h-3 w-3" />
                    Clear dates
                  </Button>
                )}
              </div>
            </div>
          )}

          <div>
            {displayedEntries.map((entry) => (
              <JournalEntryCard
                key={entry.id}
                entry={entry}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>

          {/* pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Page {page + 1} of {totalPages}
              </p>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronUp className="mr-1 h-3 w-3 rotate-[-90deg]" />
                  Previous
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronDown className="ml-1 h-3 w-3 rotate-[-90deg]" />
                </Button>
              </div>
            </div>
          )}

          {filteredJournals.length === 0 && journals.length > 0 && (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No entries matching &ldquo;{searchQuery}&rdquo;
              </p>
            </div>
          )}

          {journals.length === 0 && (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <BookOpen className="mx-auto mb-2 h-6 w-6 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No journal entries yet. Start writing above!
              </p>
            </div>
          )}
        </div>
      </div>

      {/* sidebar */}
      <div className="space-y-6">
        {/* mood trend mini */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">
              Your Mood This Week
            </CardTitle>
          </CardHeader>
          <CardContent>
            {moodTrend.length > 0 ? (
              <>
                <div className="flex items-end gap-1.5">
                  {moodTrend.slice(-7).map((point, i) => {
                    const height = (point.value / 5) * 100;
                    return (
                      <div key={i} className="group relative flex-1">
                        <div
                          className="w-full rounded-sm bg-foreground/20 transition-colors group-hover:bg-foreground/40"
                          style={{ height: `${height}%`, minHeight: 4 }}
                        />
                        <div className="absolute -top-8 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-foreground px-2 py-0.5 text-[10px] text-background group-hover:block">
                          {point.label}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
                  <span>7 days ago</span>
                  <span>Today</span>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                No mood data yet. Start journaling!
              </p>
            )}
          </CardContent>
        </Card>

        {/* quick stats */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Your Stats</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Processed entries</span>
              <span className="font-medium">{analytics?.totalEntries ?? journals.length}</span>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">This week</span>
              <span className="font-medium">
                {
                  journals.filter((j) => {
                    const d = new Date(j.entryDate);
                    const now = new Date();
                    const diff = now.getTime() - d.getTime();
                    return diff >= 0 && diff < 7 * 24 * 60 * 60 * 1000;
                  }).length
                }
              </span>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Avg. words</span>
              <span className="font-medium">
                {analytics?.avgWordCount
                  ? Math.round(analytics.avgWordCount)
                  : journals.length > 0
                    ? Math.round(
                        journals.reduce((acc, j) => acc + j.wordCount, 0) /
                          journals.length
                      )
                    : 0}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* pending prompt from therapist */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              <CardTitle className="text-sm font-medium">
                From Your Therapist
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {pendingPrompts.length > 0 ? (
              <div className="space-y-3">
                <div className="rounded-lg border border-dashed p-4">
                  <p className="text-sm italic text-muted-foreground">
                    &ldquo;{pendingPrompts[0].promptText}&rdquo;
                  </p>
                  <p className="mt-2 text-[10px] text-muted-foreground">
                    - {pendingPrompts[0].therapistName}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full text-xs"
                  onClick={() => setActivePrompt(pendingPrompts[0])}
                >
                  <Send className="mr-1 h-3 w-3" />
                  Respond to Prompt
                </Button>
                {pendingPrompts.length > 1 && (
                  <p className="text-center text-[10px] text-muted-foreground">
                    +{pendingPrompts.length - 1} more pending prompts
                  </p>
                )}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-4">
                <p className="text-sm text-muted-foreground">
                  No pending prompts right now.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
