"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Users,
  BookOpen,
  MessageSquare,
  Activity,
  TrendingUp,
  TrendingDown,
  Search,
  ArrowRight,
  Clock,
  Sparkles,
  Loader2,
} from "lucide-react";
import {
  fetchPatients,
  fetchDashboardStats,
  fetchAnalytics,
  fetchJournals,
  fetchMoodTrend,
} from "@/lib/api";
import type {
  Patient,
  JournalEntry,
  DashboardStats,
  PatientAnalytics,
  TrendDataPoint,
} from "@/types";

// stat card

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
}: {
  title: string;
  value: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  trend?: "up" | "down" | null;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
          {trend === "up" && (
            <TrendingUp className="h-3 w-3 text-emerald-500" />
          )}
          {trend === "down" && (
            <TrendingDown className="h-3 w-3 text-red-500" />
          )}
          {description}
        </div>
      </CardContent>
    </Card>
  );
}

// mini mood sparkline

function MoodSparkline({ moods }: { moods: TrendDataPoint[] }) {
  const max = 5;

  if (moods.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Mood Trend (Selected Patient)
          </CardTitle>
          <CardDescription>Last 14 days</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No mood data available.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">
          Mood Trend (Selected Patient)
        </CardTitle>
        <CardDescription>Last 14 days</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-1.5">
          {moods.map((point, i) => {
            const height = (point.value / max) * 100;
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
          <span>{moods[0]?.date.slice(5)}</span>
          <span>{moods[moods.length - 1]?.date.slice(5)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

// theme bar

function ThemeBar({
  theme,
  percentage,
}: {
  theme: string;
  percentage: number;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-44 shrink-0 text-sm capitalize text-muted-foreground" title={theme}>
        {theme}
      </span>
      <div className="flex-1">
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-foreground/70"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
      <span className="w-12 text-right text-sm font-medium">
        {percentage}%
      </span>
    </div>
  );
}

// journal timeline item

function JournalItem({ entry }: { entry: JournalEntry }) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className="h-2 w-2 rounded-full bg-foreground" />
        <div className="flex-1 border-l border-dashed" />
      </div>
      <div className="flex-1 pb-6">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {new Date(entry.entryDate).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </span>
          {entry.mood && (
            <Badge variant="outline" className="text-[10px]">
              Mood: {entry.mood}/5
            </Badge>
          )}
        </div>
        <p className="mt-1 text-sm leading-relaxed">{entry.content}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.themes.map((theme) => (
            <Badge
              key={theme}
              variant="secondary"
              className="text-[10px] capitalize"
            >
              {theme}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

// patient list item

function PatientItem({
  patient,
  isSelected,
  onClick,
  analytics,
}: {
  patient: Patient;
  isSelected: boolean;
  onClick: () => void;
  analytics: PatientAnalytics | null;
}) {
  const initials = patient.name
    .split(" ")
    .map((n) => n[0])
    .join("");

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors ${
        isSelected ? "bg-muted" : "hover:bg-muted/50"
      }`}
    >
      <Avatar className="h-9 w-9">
        <AvatarFallback className="text-xs">{initials}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{patient.name}</p>
        <p className="text-xs text-muted-foreground">
          {analytics?.totalEntries ?? 0} entries
        </p>
      </div>
    </button>
  );
}

// rag assistant panel

import ReactMarkdown from "react-markdown";

// markdown prose styles for dashboard rag panel
const ragMarkdownComponents = {
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mb-2 last:mb-0">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li>{children}</li>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="mb-1 mt-3 text-base font-semibold first:mt-0">{children}</h3>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h4 className="mb-1 mt-3 text-sm font-semibold first:mt-0">{children}</h4>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h5 className="mb-1 mt-2 text-sm font-semibold first:mt-0">{children}</h5>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="border-l-2 border-muted-foreground/30 pl-3 italic">{children}</blockquote>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="rounded bg-muted px-1 py-0.5 text-xs">{children}</code>
  ),
};

function RAGAssistantPanel({
  patients,
  selectedPatientId,
}: {
  patients: Patient[];
  selectedPatientId: string;
}) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [sourceCount, setSourceCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // clear results when patient changes
  useEffect(() => {
    setQuery("");
    setAnswer(null);
    setSourceCount(0);
    setError(null);
  }, [selectedPatientId]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const { ragSearch } = await import("@/lib/api");
      const data = await ragSearch({
        query: query.trim(),
        patientId: selectedPatientId || undefined,
        sourceType: "journal",
        topK: 5,
      });
      setAnswer(data.generatedAnswer ?? "No answer generated.");
      setSourceCount(data.results.length);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Search failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const selectedName = patients.find((p) => p.id === selectedPatientId)?.name;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          <CardTitle className="text-sm font-medium">RAG Assistant</CardTitle>
        </div>
        <CardDescription>
          {selectedName
            ? `Ask questions about ${selectedName}\u2019s journal data`
            : "Select a patient to query their journal data"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          <Input
            placeholder={
              selectedName
                ? `e.g. What themes appear in ${selectedName}\u2019s recent entries?`
                : "Select a patient from the list first"
            }
            className="flex-1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            disabled={loading}
          />
          <Button
            size="icon"
            variant="outline"
            onClick={handleSearch}
            disabled={loading || !query.trim()}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* error */}
        {error && (
          <div className="mt-3 rounded-lg border border-destructive/50 p-3">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* loading */}
        {loading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Searching journal data...
          </div>
        )}

        {/* answer */}
        {answer && !loading && (
          <div className="mt-4 space-y-2">
            <div className="rounded-lg border p-4">
              <div className="text-sm leading-relaxed">
                <ReactMarkdown components={ragMarkdownComponents}>
                  {answer}
                </ReactMarkdown>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">
                {sourceCount} sources retrieved
              </Badge>
              <span className="text-[10px] text-muted-foreground">
                Retrieved information · Not clinical advice
              </span>
            </div>
          </div>
        )}

        {/* empty state */}
        {!answer && !loading && !error && (
          <div className="mt-4 rounded-lg border border-dashed p-6 text-center">
            <p className="text-sm text-muted-foreground">
              RAG-powered responses will appear here with source citations.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              All answers are retrieved information - clinical judgment stays
              with you.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// loading skeleton

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
              <Skeleton className="mt-2 h-3 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <Card>
          <CardContent className="pt-6">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="mb-3 h-12 w-full" />
            ))}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-32" />
        </div>
      </div>
    </div>
  );
}

// main dashboard page

export default function DashboardOverview() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [analyticsMap, setAnalyticsMap] = useState<
    Record<string, PatientAnalytics>
  >({});
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [selectedJournals, setSelectedJournals] = useState<JournalEntry[]>([]);
  const [moodTrend, setMoodTrend] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(true);

  // load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        const [patientsData, statsData] = await Promise.all([
          fetchPatients(),
          fetchDashboardStats(),
        ]);
        setPatients(patientsData);
        setStats(statsData);

        // load analytics for all patients
        const analyticsResults: Record<string, PatientAnalytics> = {};
        await Promise.all(
          patientsData.map(async (p) => {
            try {
              const a = await fetchAnalytics(p.id);
              analyticsResults[p.id] = a;
            } catch {
              // analytics may not exist for all patients
            }
          })
        );
        setAnalyticsMap(analyticsResults);

        // select first patient
        if (patientsData.length > 0) {
          setSelectedPatientId(patientsData[0].id);
        }
      } catch (err) {
        console.error("failed to load dashboard data:", err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // load journals and mood for selected patient
  useEffect(() => {
    if (!selectedPatientId) return;

    const loadPatientData = async () => {
      try {
        const [journals, mood] = await Promise.all([
          fetchJournals({ patientId: selectedPatientId, limit: 10 }),
          fetchMoodTrend(selectedPatientId, 14).catch(() => []),
        ]);
        setSelectedJournals(journals);
        setMoodTrend(mood);
      } catch (err) {
        console.error("failed to load patient data:", err);
        setSelectedJournals([]);
        setMoodTrend([]);
      }
    };

    loadPatientData();
  }, [selectedPatientId]);

  if (loading) return <DashboardSkeleton />;

  const selectedAnalytics = analyticsMap[selectedPatientId] ?? null;
  const selectedPatient = patients.find((p) => p.id === selectedPatientId);

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h2 className="text-lg font-semibold">Overview</h2>
        <p className="text-sm text-muted-foreground">
          Your practice at a glance - {patients.length} patients, {stats?.totalJournals ?? 0} journal entries
        </p>
      </div>

      {/* stats row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Patients"
          value={stats?.totalPatients.toString() ?? "0"}
          description="+2 this month"
          icon={Users}
          trend="up"
        />
        <StatCard
          title="Journal Entries"
          value={stats?.totalJournals.toString() ?? "0"}
          description="+18 this week"
          icon={BookOpen}
          trend="up"
        />
        <StatCard
          title="Conversations"
          value={stats?.totalConversations.toLocaleString() ?? "0"}
          description="Indexed in vector store"
          icon={MessageSquare}
        />
        <StatCard
          title="Active Patients"
          value={`${stats?.activePatients ?? 0}/${stats?.totalPatients ?? 0}`}
          description="Journaled in the last 7 days"
          icon={Activity}
          trend={stats?.activePatients && stats.activePatients > 0 ? "up" : null}
        />
      </div>

      {/* main grid */}
      <div className="flex gap-6">
        {/* patient list sidebar */}
        <div className="hidden w-[240px] shrink-0 lg:block">
          <Card className="flex h-full flex-col">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Patients</CardTitle>
              <CardDescription>
                {patients.length} active patients
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden px-2">
              <ScrollArea className="h-full">
                <div className="space-y-0.5 px-1">
                  {patients.map((patient) => (
                    <PatientItem
                      key={patient.id}
                      patient={patient}
                      isSelected={patient.id === selectedPatientId}
                      onClick={() => setSelectedPatientId(patient.id)}
                      analytics={analyticsMap[patient.id] ?? null}
                    />
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* right column */}
        <div className="min-w-0 flex-1 space-y-6">
          {/* patient analytics */}
          {selectedPatient && selectedAnalytics && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-medium">
                      {selectedPatient.name} - Analytics
                    </CardTitle>
                    <CardDescription>
                      {selectedAnalytics.totalEntries} entries over{" "}
                      {selectedAnalytics.dateRange?.spanDays ?? 0} days
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/dashboard/patients/${selectedPatientId}`}>
                      View Full Profile
                      <ArrowRight className="ml-1 h-3 w-3" />
                    </Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-6 sm:grid-cols-2">
                  {/* topic distribution */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Topic Distribution
                    </h4>
                    <div className="space-y-2">
                      {selectedAnalytics.topicDistribution
                        .slice(0, 6)
                        .map((t) => (
                          <ThemeBar
                            key={t.topicId}
                            theme={t.label}
                            percentage={t.percentage}
                          />
                        ))}
                    </div>
                  </div>

                  {/* quick stats */}
                  <div className="space-y-4">
                    <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Summary
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg border p-3 text-center">
                        <div className="text-lg font-bold">
                          {selectedAnalytics.totalEntries}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          Total entries
                        </div>
                      </div>
                      <div className="rounded-lg border p-3 text-center">
                        <div className="text-lg font-bold">
                          {selectedAnalytics.avgWordCount}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          Avg. words
                        </div>
                      </div>
                      <div className="rounded-lg border p-3 text-center">
                        <div className="text-lg font-bold">
                          {selectedAnalytics.dateRange?.spanDays ?? "-"}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          Span (days)
                        </div>
                      </div>
                      <div className="rounded-lg border p-3 text-center" title={selectedAnalytics.topicDistribution[0]?.label}>
                        <div className="text-sm font-bold capitalize break-words leading-tight">
                          {selectedAnalytics.topicDistribution[0]?.label ?? "-"}
                        </div>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">
                          Top topic
                        </div>
                      </div>
                    </div>

                    {/* entry frequency */}
                    <div className="pt-2 mt-2 border-t">
                      <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Monthly Frequency
                      </h4>
                      <div className="flex items-end gap-1">
                        {selectedAnalytics.entryFrequency.map((ef) => {
                          const maxCount = Math.max(
                            ...selectedAnalytics.entryFrequency.map(
                              (x) => x.count
                            )
                          );
                          const heightPct = (ef.count / maxCount) * 100;
                          return (
                            <div
                              key={ef.month}
                              className="group relative flex-1"
                            >
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
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* mood sparkline */}
          <MoodSparkline moods={moodTrend} />

          {/* rag assistant */}
          <RAGAssistantPanel
            patients={patients}
            selectedPatientId={selectedPatientId}
          />
        </div>
      </div>

      {/* recent timeline */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">
              Recent Journal Entries -{" "}
              {selectedPatient?.name ?? "Select a patient"}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {selectedJournals.length > 0 ? (
            <div className="space-y-0">
              {selectedJournals.map((entry) => (
                <JournalItem key={entry.id} entry={entry} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed p-8 text-center">
              <p className="text-sm text-muted-foreground">
                No journal entries found for this patient.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
