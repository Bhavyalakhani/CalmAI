"use client";

import { useState, useEffect, useCallback } from "react";
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
} from "lucide-react";
import { fetchJournals, fetchMoodTrend, submitJournal } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { JournalEntry, MoodScore, TrendDataPoint, Patient } from "@/types";

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

// journal entry card

function JournalEntryCard({ entry }: { entry: JournalEntry }) {
  return (
    <div className="group relative flex gap-4">
      {/* timeline dot & line */}
      <div className="flex flex-col items-center pt-1">
        <div className="h-2.5 w-2.5 rounded-full border-2 border-foreground bg-background" />
        <div className="flex-1 border-l border-dashed border-muted-foreground/30" />
      </div>

      {/* content */}
      <div className="flex-1 pb-8">
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
        </div>

        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {entry.content}
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {entry.themes.map((theme) => (
            <Badge
              key={theme}
              variant="secondary"
              className="text-[10px] capitalize"
            >
              {theme}
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

  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [moodTrend, setMoodTrend] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState("");
  const [mood, setMood] = useState<MoodScore | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAllEntries, setShowAllEntries] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  const wordCount = content.trim().split(/\s+/).filter(Boolean).length;
  const displayedEntries = showAllEntries ? journals : journals.slice(0, 5);

  const loadData = useCallback(async () => {
    if (!patient?.id) return;
    try {
      const [journalData, moodData] = await Promise.all([
        fetchJournals({ patientId: patient.id }),
        fetchMoodTrend(patient.id, 14).catch(() => []),
      ]);
      setJournals(journalData);
      setMoodTrend(moodData);
    } catch (err) {
      console.error("failed to load journal data:", err);
    } finally {
      setLoading(false);
    }
  }, [patient?.id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setIsSubmitting(true);
    setSubmitMessage(null);

    try {
      await submitJournal(content, mood ?? undefined);
      setContent("");
      setMood(null);
      setSubmitMessage("Entry saved successfully!");
      // reload journals
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to save entry";
      setSubmitMessage(message);
    } finally {
      setIsSubmitting(false);
    }
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
        {/* new entry */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              <CardTitle className="text-sm font-medium">
                New Journal Entry
              </CardTitle>
            </div>
            <CardDescription>
              Write about your day, thoughts, or feelings. Your therapist can
              see your entries to provide better support.
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
                <span className="text-xs text-muted-foreground">
                  {wordCount} words
                </span>
                <Button
                  onClick={handleSubmit}
                  disabled={!content.trim() || isSubmitting}
                  size="sm"
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
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-medium">Your Journal Timeline</h2>
            <Badge variant="outline" className="text-[10px]">
              {journals.length} entries
            </Badge>
          </div>

          <div>
            {displayedEntries.map((entry) => (
              <JournalEntryCard key={entry.id} entry={entry} />
            ))}
          </div>

          {journals.length > 5 && (
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={() => setShowAllEntries(!showAllEntries)}
            >
              {showAllEntries ? (
                <>
                  <ChevronUp className="mr-1 h-3 w-3" />
                  Show less
                </>
              ) : (
                <>
                  <ChevronDown className="mr-1 h-3 w-3" />
                  Show all {journals.length} entries
                </>
              )}
            </Button>
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
              <span className="text-muted-foreground">Total entries</span>
              <span className="font-medium">{journals.length}</span>
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
                    return diff < 7 * 24 * 60 * 60 * 1000;
                  }).length
                }
              </span>
            </div>
            <Separator />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Avg. words</span>
              <span className="font-medium">
                {journals.length > 0
                  ? Math.round(
                      journals.reduce((acc, j) => acc + j.wordCount, 0) /
                        journals.length
                    )
                  : 0}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* therapist prompt placeholder */}
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
            <div className="rounded-lg border border-dashed p-4">
              <p className="text-sm italic text-muted-foreground">
                &ldquo;This week, try writing about one moment where you
                noticed your anxiety and how you responded to it.&rdquo;
              </p>
              <p className="mt-2 text-[10px] text-muted-foreground">
                - Your Therapist
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
