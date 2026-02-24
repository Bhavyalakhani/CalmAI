// patient insights page — analytics from journal entries
// shows topic distribution, mood trend, topics over time, representative entries, streaks

"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  LineChart,
  TrendingUp,
  Activity,
  Brain,
  Calendar,
  BookOpen,
  Flame,
} from "lucide-react";
import { fetchAnalytics, fetchMoodTrend, fetchJournals } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { PatientAnalytics, Patient, TrendDataPoint, JournalEntry } from "@/types";

// compute writing streak from sorted journal entries
function computeStreak(journals: JournalEntry[]): { current: number; longest: number } {
  if (journals.length === 0) return { current: 0, longest: 0 };

  const dates = [...new Set(journals.map((j) => j.entryDate.slice(0, 10)))].sort().reverse();
  let current = 0;
  let longest = 0;
  let streak = 1;

  // check if today or yesterday has an entry for current streak
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const hasRecent = dates[0] === today || dates[0] === yesterday;

  for (let i = 1; i < dates.length; i++) {
    const prev = new Date(dates[i - 1]);
    const curr = new Date(dates[i]);
    const diff = (prev.getTime() - curr.getTime()) / 86400000;
    if (diff <= 1.5) {
      streak++;
    } else {
      if (i === 1 || (i > 1 && longest < streak)) longest = Math.max(longest, streak);
      streak = 1;
    }
  }
  longest = Math.max(longest, streak);
  current = hasRecent ? streak : 0;

  // recalculate current streak from the most recent date
  if (hasRecent) {
    current = 1;
    for (let i = 1; i < dates.length; i++) {
      const prev = new Date(dates[i - 1]);
      const curr = new Date(dates[i]);
      const diff = (prev.getTime() - curr.getTime()) / 86400000;
      if (diff <= 1.5) {
        current++;
      } else {
        break;
      }
    }
  }

  return { current, longest };
}

// topics over time line chart with topic selector

import type { TopicOverTime } from "@/types";

function TopicsOverTimeChart({ data }: { data: TopicOverTime[] }) {
  const months = [...new Set(data.map((t) => t.month))].sort();
  const topicMap = new Map<number, { label: string; freqs: Map<string, number> }>();
  for (const t of data) {
    if (!topicMap.has(t.topicId)) {
      topicMap.set(t.topicId, { label: t.label, freqs: new Map() });
    }
    topicMap.get(t.topicId)!.freqs.set(t.month, t.frequency);
  }
  const allTopics = [...topicMap.entries()];

  const [selectedId, setSelectedId] = useState<number | "all">("all");

  const visibleTopics = selectedId === "all"
    ? allTopics
    : allTopics.filter(([id]) => id === selectedId);

  const maxFreq = Math.max(
    ...visibleTopics.flatMap(([, { freqs }]) => [...freqs.values()]),
    1
  );

  const color = "#a1a1aa";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm">Topics Over Time</CardTitle>
            <CardDescription>
              How your journal topics shift month to month
            </CardDescription>
          </div>
          <select
            value={String(selectedId)}
            onChange={(e) =>
              setSelectedId(e.target.value === "all" ? "all" : Number(e.target.value))
            }
            className="h-8 rounded-md border border-input bg-background px-2 text-xs capitalize"
          >
            <option value="all">All topics</option>
            {allTopics.map(([id, { label }]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardContent>
        {/* y-axis + chart area */}
        <div className="flex gap-2">
          {/* y-axis labels */}
          <div className="flex flex-col justify-between text-[10px] text-muted-foreground" style={{ height: 160 }}>
            <span>{maxFreq}</span>
            <span>{Math.round(maxFreq / 2)}</span>
            <span>0</span>
          </div>
          {/* SVG line chart */}
          <div className="relative flex-1" style={{ height: 160 }}>
            {/* horizontal grid lines */}
            <div className="absolute inset-0 flex flex-col justify-between pointer-events-none">
              {[0, 1, 2].map((i) => (
                <div key={i} className="border-t border-muted/40" />
              ))}
            </div>
            <svg
              viewBox={`0 0 ${Math.max(months.length - 1, 1) * 100} 100`}
              className="h-full w-full"
              preserveAspectRatio="none"
            >
              {visibleTopics.map(([topicId, { freqs }]) => {
                const points = months.map((m, i) => {
                  const val = freqs.get(m) ?? 0;
                  const x = months.length === 1 ? 50 : (i / (months.length - 1)) * (months.length - 1) * 100;
                  const y = 100 - (val / maxFreq) * 90 - 5;
                  return `${x},${y}`;
                });
                return (
                  <polyline
                    key={topicId}
                    points={points.join(" ")}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
              {visibleTopics.map(([topicId, { label, freqs }]) =>
                months.map((m, i) => {
                  const val = freqs.get(m) ?? 0;
                  if (val === 0) return null;
                  const cx = months.length === 1 ? 50 : (i / (months.length - 1)) * (months.length - 1) * 100;
                  const cy = 100 - (val / maxFreq) * 90 - 5;
                  return (
                    <circle
                      key={`${topicId}-${m}`}
                      cx={cx}
                      cy={cy}
                      r="4"
                      fill={color}
                      vectorEffect="non-scaling-stroke"
                    >
                      <title>{label}: {val} ({m})</title>
                    </circle>
                  );
                })
              )}
            </svg>
          </div>
        </div>
        {/* x-axis labels */}
        <div className="ml-8 mt-1 flex justify-between text-[10px] text-muted-foreground">
          {months.map((m) => (
            <span key={m}>{m.slice(5)}</span>
          ))}
        </div>
        {/* legend for "all" mode */}
        {selectedId === "all" && visibleTopics.length > 1 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {allTopics.map(([topicId, { label }]) => (
              <button
                key={topicId}
                onClick={() => setSelectedId(topicId)}
                className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] capitalize text-muted-foreground transition-colors hover:bg-muted"
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function InsightsPage() {
  const { user } = useAuth();
  const patient = user as Patient | null;
  const [analytics, setAnalytics] = useState<PatientAnalytics | null>(null);
  const [moodTrend, setMoodTrend] = useState<TrendDataPoint[]>([]);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patient?.id) return;
    Promise.all([
      fetchAnalytics(patient.id).catch(() => null),
      fetchMoodTrend(patient.id, 30).catch(() => []),
      fetchJournals({ patientId: patient.id, limit: 200 }).catch(() => []),
    ])
      .then(([analyticsData, moodData, journalData]) => {
        setAnalytics(analyticsData);
        setMoodTrend(moodData);
        setJournals(journalData);
      })
      .catch((err) => console.error("failed to load insights:", err))
      .finally(() => setLoading(false));
  }, [patient?.id]);

  const streak = computeStreak(journals);

  // compute mood average from trend data
  const moodAvg = moodTrend.length > 0
    ? (moodTrend.reduce((s, p) => s + p.value, 0) / moodTrend.length).toFixed(1)
    : null;

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">No analytics data available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Your Insights</h2>
        <p className="text-sm text-muted-foreground">
          Analytics generated from your journal entries. These are patterns, not
          diagnoses.
        </p>
      </div>

      {/* summary stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Processed Entries
            </CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics.totalEntries}</div>
            <p className="text-xs text-muted-foreground">
              Over {analytics.dateRange?.spanDays ?? 0} days
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg. Words
            </CardTitle>
            <LineChart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analytics.avgWordCount}</div>
            <p className="text-xs text-muted-foreground">Per entry</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Top Topic
            </CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">
              {analytics.topicDistribution[0]?.label ?? "-"}
            </div>
            <p className="text-xs text-muted-foreground">
              {analytics.topicDistribution[0]?.percentage ?? 0}% of entries
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Writing Streak
            </CardTitle>
            <Flame className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{streak.current} days</div>
            <p className="text-xs text-muted-foreground">
              Longest: {streak.longest} days
            </p>
          </CardContent>
        </Card>
      </div>

      {/* mood trend */}
      {moodTrend.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm">Mood Trend (30 days)</CardTitle>
                <CardDescription>
                  Your daily mood scores over the past month
                </CardDescription>
              </div>
              {moodAvg && (
                <div className="flex items-center gap-1 text-sm">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium">{moodAvg}</span>
                  <span className="text-xs text-muted-foreground">avg</span>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-1.5" style={{ height: 80 }}>
              {moodTrend.map((point, i) => {
                const height = (point.value / 5) * 100;
                return (
                  <div key={i} className="group relative flex-1">
                    <div
                      className="w-full rounded-sm bg-foreground/20 transition-colors group-hover:bg-foreground/40"
                      style={{ height: `${height}%`, minHeight: 4 }}
                    />
                    <div className="absolute -top-8 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-foreground px-2 py-0.5 text-[10px] text-background group-hover:block">
                      {point.label} · {point.value}/5
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

      {/* topic distribution */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Topic Distribution</CardTitle>
          <CardDescription>
            BERTopic model classification of your journal entries
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {analytics.topicDistribution.map((td) => (
            <div key={td.topicId} className="flex items-center gap-3">
              <span className="w-32 shrink-0 text-sm capitalize text-muted-foreground" title={td.label}>
                {td.label}
              </span>
              <div className="flex-1">
                <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-foreground/60"
                    style={{ width: `${td.percentage}%` }}
                  />
                </div>
              </div>
              <span className="w-12 text-right text-sm font-medium">
                {td.percentage}%
              </span>
              <Badge variant="outline" className="text-[10px]">
                {td.count}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* topics over time — line chart with topic selector */}
      {analytics.topicsOverTime.length > 0 && (
        <TopicsOverTimeChart data={analytics.topicsOverTime} />
      )}

      {/* representative entries */}
      {analytics.representativeEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Representative Entries</CardTitle>
            <CardDescription>
              Journal entries that best capture each topic
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {analytics.representativeEntries.map((re) => (
              <div key={`${re.topicId}-${re.journalId}`} className="rounded-lg border p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="text-[10px] capitalize">
                    {re.label}
                  </Badge>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(re.probability * 100)}% match
                    </span>
                    {re.entryDate && (
                      <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                        <Calendar className="h-2.5 w-2.5" />
                        {new Date(re.entryDate).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  {re.content}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* monthly frequency */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Monthly Writing Frequency</CardTitle>
          <CardDescription>How often you write each month</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            {analytics.entryFrequency.map((ef) => {
              const maxCount = Math.max(
                ...analytics.entryFrequency.map((x) => x.count)
              );
              const heightPct = (ef.count / maxCount) * 100;
              return (
                <div
                  key={ef.month}
                  className="group relative flex flex-1 flex-col items-center"
                >
                  <div className="absolute -top-6 hidden rounded bg-foreground px-1.5 py-0.5 text-[10px] text-background group-hover:block">
                    {ef.count} entries
                  </div>
                  <div
                    className="w-full rounded-md bg-foreground/20 transition-colors group-hover:bg-foreground/40"
                    style={{ height: `${heightPct}%`, minHeight: 8, maxHeight: 80 }}
                  />
                  <span className="mt-2 text-xs text-muted-foreground">
                    {ef.month.slice(5)}
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* disclaimer */}
      <div className="rounded-lg border border-dashed p-4">
        <p className="text-xs text-muted-foreground">
          <Brain className="mr-1 inline h-3 w-3" />
          These insights are generated from BERTopic model analysis of your
          journal entries. They are informational patterns, not clinical
          assessments. Please discuss any concerns with your therapist.
        </p>
      </div>
    </div>
  );
}
