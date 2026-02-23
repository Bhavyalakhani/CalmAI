"use client";

// patient analytics explorer — per-patient deep dives, topic trends, representative entries
// replaces the old bias-focused page with meaningful clinical intelligence

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Bar, BarChart, XAxis, YAxis, CartesianGrid } from "recharts";
import {
  BarChart3,
  Users,
  BookOpen,
  Calendar,
  FileText,
  TrendingUp,
  Activity,
  MessageSquare,
} from "lucide-react";
import {
  fetchPatients,
  fetchAnalytics,
  fetchDashboardStats,
  fetchConversationTopics,
  fetchConversationSeverities,
} from "@/lib/api";
import type { Patient, PatientAnalytics, DashboardStats } from "@/types";

// topic distribution bar with full label

function TopicBar({
  label,
  percentage,
  count,
}: {
  label: string;
  percentage: number;
  count: number;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm capitalize">{label}</span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {percentage.toFixed(1)}% ({count})
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-foreground/60"
          style={{ width: `${Math.max(percentage, 1)}%` }}
        />
      </div>
    </div>
  );
}

// format iso date to readable string
function fmtDate(raw: string | undefined) {
  if (!raw) return "";
  try {
    return new Date(raw).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return raw;
  }
}

// severity dot indicator

function severityDot(severity: string) {
  switch (severity) {
    case "crisis":
      return "bg-red-500";
    case "severe":
      return "bg-orange-500";
    case "moderate":
      return "bg-yellow-500";
    case "mild":
      return "bg-green-500";
    default:
      return "bg-zinc-500";
  }
}

export default function AnalyticsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [analyticsList, setAnalyticsList] = useState<
    Record<string, PatientAnalytics>
  >({});
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [conversationTopics, setConversationTopics] = useState<
    { label: string; count: number }[]
  >([]);
  const [conversationSeverities, setConversationSeverities] = useState<
    { label: string; count: number }[]
  >([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [patientsData, statsData, topicData, severityData] =
          await Promise.all([
            fetchPatients(),
            fetchDashboardStats(),
            fetchConversationTopics(),
            fetchConversationSeverities(),
          ]);
        setPatients(patientsData);
        setStats(statsData);
        setConversationTopics(topicData.topics ?? []);
        setConversationSeverities(severityData.severities ?? []);

        // load analytics for all patients in parallel
        const analyticsMap: Record<string, PatientAnalytics> = {};
        await Promise.all(
          patientsData.map(async (p) => {
            try {
              const a = await fetchAnalytics(p.id);
              analyticsMap[p.id] = a;
            } catch {
              // skip patients without analytics
            }
          })
        );
        setAnalyticsList(analyticsMap);

        // select first patient with analytics
        const firstWithAnalytics = patientsData.find(
          (p) => analyticsMap[p.id]
        );
        if (firstWithAnalytics) {
          setSelectedPatientId(firstWithAnalytics.id);
        } else if (patientsData.length > 0) {
          setSelectedPatientId(patientsData[0].id);
        }
      } catch (err) {
        console.error("failed to load analytics data:", err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-[500px]" />
      </div>
    );
  }

  // aggregates
  const analyticsValues = Object.values(analyticsList);
  const totalEntries = analyticsValues.reduce(
    (sum, a) => sum + a.totalEntries,
    0
  );
  const avgWordCount =
    analyticsValues.length > 0
      ? Math.round(
          analyticsValues.reduce((sum, a) => sum + a.avgWordCount, 0) /
            analyticsValues.length
        )
      : 0;
  const totalConversationHits = conversationSeverities.reduce(
    (sum, s) => sum + s.count,
    0
  );

  const selected = analyticsList[selectedPatientId] ?? null;
  const selectedPatient = patients.find((p) => p.id === selectedPatientId);

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h2 className="text-lg font-semibold">Patient Analytics</h2>
        <p className="text-sm text-muted-foreground">
          Deep dive into individual patient data, topic trends, and corpus
          insights
        </p>
      </div>

      {/* summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Journal Entries
            </CardTitle>
            <BookOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalEntries}</div>
            <p className="text-xs text-muted-foreground">
              Across {analyticsValues.length} patients with analytics
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg. Word Count
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgWordCount}</div>
            <p className="text-xs text-muted-foreground">
              Words per journal entry (patient avg)
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Conversations Corpus
            </CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(stats?.totalConversations ?? 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {conversationTopics.length} topics ·{" "}
              {conversationSeverities.length} severity levels
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Patients
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.activePatients ?? 0}/{stats?.totalPatients ?? 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Journaled in the last 7 days
            </p>
          </CardContent>
        </Card>
      </div>

      {/* main tabs */}
      <Tabs defaultValue="patient">
        <TabsList>
          <TabsTrigger value="patient">Patient Deep Dive</TabsTrigger>
          <TabsTrigger value="compare">Patient Comparison</TabsTrigger>
          <TabsTrigger value="corpus">Conversations Corpus</TabsTrigger>
        </TabsList>

        {/* patient deep dive tab */}
        <TabsContent value="patient" className="mt-4 space-y-6">
          {/* patient selector */}
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium">Patient:</span>
            <Select
              value={selectedPatientId}
              onValueChange={setSelectedPatientId}
            >
              <SelectTrigger className="w-[280px]">
                <SelectValue placeholder="Select a patient" />
              </SelectTrigger>
              <SelectContent>
                {patients.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    <span>{p.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      ({analyticsList[p.id]?.totalEntries ?? 0} entries)
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selected ? (
            <div className="grid gap-6 lg:grid-cols-2">
              {/* overview stats */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    {selectedPatient?.name ?? "Patient"} — Overview
                  </CardTitle>
                  <CardDescription>
                    {selected.totalEntries} entries over{" "}
                    {selected.dateRange?.spanDays ?? 0} days
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border p-3 text-center">
                      <div className="text-2xl font-bold">
                        {selected.totalEntries}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Total entries
                      </div>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <div className="text-2xl font-bold">
                        {selected.avgWordCount}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Avg. words / entry
                      </div>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <div className="text-2xl font-bold">
                        {selected.dateRange?.spanDays ?? "-"}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Date span (days)
                      </div>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <div className="text-2xl font-bold">
                        {selected.topicDistribution.length}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Topics identified
                      </div>
                    </div>
                  </div>

                  {/* date range */}
                  {selected.dateRange && (
                    <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5" />
                      {fmtDate(selected.dateRange.first)} to {fmtDate(selected.dateRange.last)}
                    </div>
                  )}

                  {/* model info */}
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <Activity className="h-3.5 w-3.5" />
                    Model: {selected.modelVersion}
                  </div>
                </CardContent>
              </Card>

              {/* topic distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Topic Distribution</CardTitle>
                  <CardDescription>
                    BERTopic-discovered themes in journal entries
                  </CardDescription>
                </CardHeader>
                <CardContent className="overflow-hidden">
                  <ScrollArea className="h-[320px] pr-3">
                    <div className="space-y-3">
                      {selected.topicDistribution.map((t) => (
                        <TopicBar
                          key={t.topicId}
                          label={t.label}
                          percentage={t.percentage}
                          count={t.count}
                        />
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* entry frequency */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Entry Frequency</CardTitle>
                  <CardDescription>Monthly journaling volume</CardDescription>
                </CardHeader>
                <CardContent>
                  {selected.entryFrequency.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No frequency data available.
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {selected.entryFrequency.map((ef) => {
                        const maxCount = Math.max(
                          ...selected.entryFrequency.map((x) => x.count),
                          1
                        );
                        const pct = (ef.count / maxCount) * 100;
                        return (
                          <div key={ef.month} className="space-y-1">
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">
                                {ef.month}
                              </span>
                              <span className="font-medium">
                                {ef.count} entries
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-foreground/50"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* topics over time */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Topics Over Time</CardTitle>
                  <CardDescription>
                    How topic frequency changes month to month
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {selected.topicsOverTime.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No temporal topic data available.
                    </p>
                  ) : (
                    <ScrollArea className="h-[300px] pr-3">
                      <div className="space-y-3">
                        {(() => {
                          // group by month
                          const byMonth: Record<
                            string,
                            { label: string; frequency: number }[]
                          > = {};
                          for (const t of selected.topicsOverTime) {
                            if (!byMonth[t.month]) byMonth[t.month] = [];
                            byMonth[t.month].push({
                              label: t.label,
                              frequency: t.frequency,
                            });
                          }
                          return Object.entries(byMonth)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([month, topics]) => (
                              <div key={month}>
                                <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                                  {month}
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {topics
                                    .sort(
                                      (a, b) => b.frequency - a.frequency
                                    )
                                    .map((t) => (
                                      <Badge
                                        key={`${month}-${t.label}`}
                                        variant="secondary"
                                        className="text-[10px] capitalize"
                                      >
                                        {t.label} ({t.frequency})
                                      </Badge>
                                    ))}
                                </div>
                              </div>
                            ));
                        })()}
                      </div>
                    </ScrollArea>
                  )}
                </CardContent>
              </Card>

              {/* representative entries */}
              {selected.representativeEntries.length > 0 && (
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="text-sm">
                      Representative Entries
                    </CardTitle>
                    <CardDescription>
                      Journal excerpts that best represent each discovered topic
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {selected.representativeEntries.map((re) => (
                        <div
                          key={`${re.topicId}-${re.journalId}`}
                          className="rounded-lg border p-4"
                        >
                          <div className="mb-2 flex items-center gap-2">
                            <Badge
                              variant="secondary"
                              className="text-[10px] capitalize"
                            >
                              {re.label}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground">
                              {fmtDate(re.entryDate)} · {(re.probability * 100).toFixed(0)}%
                              confidence
                            </span>
                          </div>
                          <p className="text-sm leading-relaxed text-muted-foreground">
                            &ldquo;{re.content}&rdquo;
                          </p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-16">
                <BarChart3 className="h-10 w-10 text-muted-foreground" />
                <p className="text-sm font-medium">No analytics available</p>
                <p className="text-xs text-muted-foreground">
                  This patient does not have computed analytics yet. Run the
                  data pipeline to generate topic models.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* patient comparison tab */}
        <TabsContent value="compare" className="mt-4 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* entry count comparison */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Entries per Patient
                </CardTitle>
                <CardDescription>
                  Total journal entries and writing volume by patient
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {patients
                    .map((p) => ({
                      patient: p,
                      analytics: analyticsList[p.id],
                    }))
                    .sort(
                      (a, b) =>
                        (b.analytics?.totalEntries ?? 0) -
                        (a.analytics?.totalEntries ?? 0)
                    )
                    .map(({ patient, analytics: a }) => {
                      const entries = a?.totalEntries ?? 0;
                      const maxEntries = Math.max(
                        ...analyticsValues.map((x) => x.totalEntries),
                        1
                      );
                      return (
                        <div key={patient.id} className="space-y-1">
                          <div className="flex items-baseline justify-between">
                            <span className="text-sm">{patient.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {entries} entries · avg {a?.avgWordCount ?? 0}{" "}
                              words
                            </span>
                          </div>
                          <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-foreground/60"
                              style={{
                                width: `${(entries / maxEntries) * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>

            {/* top topics per patient */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Top Topics per Patient
                </CardTitle>
                <CardDescription>
                  Most prominent theme for each patient
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {patients.map((p) => {
                    const a = analyticsList[p.id];
                    const topTopic = a?.topicDistribution[0];
                    return (
                      <div
                        key={p.id}
                        className="flex items-center justify-between rounded-lg border px-3 py-2"
                      >
                        <span className="text-sm">{p.name}</span>
                        {topTopic ? (
                          <div className="flex items-center gap-2">
                            <Badge
                              variant="secondary"
                              className="text-[10px] capitalize"
                            >
                              {topTopic.label}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {topTopic.percentage.toFixed(0)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            No data
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* activity span chart */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-sm">
                  Journaling Span
                </CardTitle>
                <CardDescription>
                  Days between first and last journal entry per patient
                </CardDescription>
              </CardHeader>
              <CardContent>
                {(() => {
                  const chartData = patients
                    .map((p) => {
                      const a = analyticsList[p.id];
                      return {
                        name: p.name.split(" ")[0],
                        span: a?.dateRange?.spanDays ?? 0,
                        entries: a?.totalEntries ?? 0,
                      };
                    })
                    .filter((d) => d.span > 0)
                    .sort((a, b) => b.span - a.span);

                  if (chartData.length === 0) {
                    return (
                      <p className="text-sm text-muted-foreground">
                        No date range data available.
                      </p>
                    );
                  }

                  const chartConfig: ChartConfig = {
                    span: {
                      label: "Span (days)",
                      color: "var(--foreground)",
                    },
                  };

                  return (
                    <ChartContainer
                      config={chartConfig}
                      className="h-[280px] w-full"
                    >
                      <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ left: 0, right: 16, top: 0, bottom: 0 }}
                      >
                        <CartesianGrid horizontal={false} strokeDasharray="3 3" />
                        <XAxis type="number" tickLine={false} axisLine={false} />
                        <YAxis
                          type="category"
                          dataKey="name"
                          tickLine={false}
                          axisLine={false}
                          width={72}
                        />
                        <ChartTooltip
                          content={
                            <ChartTooltipContent
                              formatter={(value, _name, item) =>
                                `${value} days (${item.payload.entries} entries)`
                              }
                            />
                          }
                        />
                        <Bar
                          dataKey="span"
                          fill="var(--foreground)"
                          opacity={0.5}
                          radius={[0, 4, 4, 0]}
                        />
                      </BarChart>
                    </ChartContainer>
                  );
                })()}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* conversation corpus tab */}
        <TabsContent value="corpus" className="mt-4 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* topic distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Conversations Topic Distribution
                </CardTitle>
                <CardDescription>
                  {conversationTopics.length} topics discovered across{" "}
                  {(stats?.totalConversations ?? 0).toLocaleString()}{" "}
                  conversations
                </CardDescription>
              </CardHeader>
              <CardContent className="overflow-hidden">
                <ScrollArea className="h-[400px] pr-3">
                  <div className="space-y-3">
                    {conversationTopics.map((t) => {
                      const pct =
                        totalConversationHits > 0
                          ? (t.count / totalConversationHits) * 100
                          : 0;
                      return (
                        <TopicBar
                          key={t.label}
                          label={t.label}
                          percentage={pct}
                          count={t.count}
                        />
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* severity distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Severity Distribution
                </CardTitle>
                <CardDescription>
                  Conversations severity classification
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {conversationSeverities.map((s) => {
                    const pct =
                      totalConversationHits > 0
                        ? (s.count / totalConversationHits) * 100
                        : 0;
                    return (
                      <div key={s.label} className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div
                              className={`h-2.5 w-2.5 rounded-full ${severityDot(s.label)}`}
                            />
                            <span className="text-sm capitalize">
                              {s.label}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {s.count.toLocaleString()} ({pct.toFixed(1)}%)
                          </span>
                        </div>
                        <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-foreground/50"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                <Separator className="my-4" />

                <div className="rounded-lg border border-dashed p-3">
                  <p className="text-xs text-muted-foreground">
                    <TrendingUp className="mr-1 inline h-3 w-3" />
                    The conversations corpus contains{" "}
                    {totalConversationHits.toLocaleString()} classified
                    exchanges. Topics and severities are assigned via
                    BERTopic classification from the data pipeline.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
