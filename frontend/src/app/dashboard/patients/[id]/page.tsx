// patient profile page - therapist view of a single patient
// shows patient info, analytics, and full journal timeline with filters

"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  ArrowLeft,
  Calendar,
  Mail,
  BookOpen,
  Activity,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import {
  fetchPatient,
  fetchAnalytics,
  fetchJournals,
  fetchMoodTrend,
} from "@/lib/api";
import type {
  Patient,
  PatientAnalytics,
  JournalEntry,
  TrendDataPoint,
  JournalTheme,
} from "@/types";

const ALL_THEMES: JournalTheme[] = [
  "anxiety",
  "depression",
  "positive",
  "negative",
  "therapy",
  "sleep",
  "social",
  "work",
];

const PAGE_SIZE = 20;

export default function PatientProfilePage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.id as string;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [analytics, setAnalytics] = useState<PatientAnalytics | null>(null);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [moodTrend, setMoodTrend] = useState<TrendDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [journalsLoading, setJournalsLoading] = useState(false);

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
        const [patientData, analyticsData, journalData, moodData] =
          await Promise.all([
            fetchPatient(patientId),
            fetchAnalytics(patientId).catch(() => null),
            fetchJournals({ patientId, limit: 200 }),
            fetchMoodTrend(patientId, 30).catch(() => []),
          ]);
        setPatient(patientData);
        setAnalytics(analyticsData);
        setAllJournals(journalData);
        setMoodTrend(moodData);
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
        j.themes.includes(themeFilter as JournalTheme)
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
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
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

  return (
    <div className="space-y-6">
      {/* header */}
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
              <p className="text-xs text-muted-foreground">Total Entries</p>
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
              <p className="text-xs text-muted-foreground">Top Theme</p>
              <p className="text-sm font-medium capitalize">
                {analytics?.themeDistribution[0]?.theme ?? "-"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* main content */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* journal entries */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Journal Entries
              </CardTitle>
              <CardDescription>
                {journals.length} entries
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
                    <SelectValue placeholder="Theme" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All themes</SelectItem>
                    {ALL_THEMES.map((t) => (
                      <SelectItem key={t} value={t}>
                        <span className="capitalize">{t}</span>
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
                        entries)
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
                    No journal entries found
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
          {/* theme distribution */}
          {analytics && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  Theme Distribution
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {analytics.themeDistribution.map((t) => (
                  <div key={t.theme} className="flex items-center gap-3">
                    <span className="w-24 text-xs capitalize text-muted-foreground">
                      {t.theme}
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
                      Total entries
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
                      {analytics.themeDistribution[0]?.theme ?? "-"}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      Top theme
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
        </div>
      </div>
    </div>
  );
}
