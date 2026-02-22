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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BarChart3,
  PieChart,
  AlertTriangle,
  Users,
} from "lucide-react";
import {
  fetchPatients,
  fetchAnalytics,
  fetchDashboardStats,
} from "@/lib/api";
import type { Patient, PatientAnalytics, DashboardStats } from "@/types";

// bias distribution bar

function DistributionBar({
  label,
  value,
  total,
  flagged,
}: {
  label: string;
  value: number;
  total: number;
  flagged?: boolean;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 text-sm capitalize text-muted-foreground">
        {label}
      </span>
      <div className="flex-1">
        <div className="h-3 overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${
              flagged ? "bg-destructive/60" : "bg-foreground/60"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
      <span className="w-16 text-right text-sm font-medium">
        {pct.toFixed(1)}%
      </span>
      {flagged && (
        <Badge variant="destructive" className="text-[10px]">
          <AlertTriangle className="mr-1 h-3 w-3" />
          Low
        </Badge>
      )}
    </div>
  );
}

export default function AnalyticsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [analyticsList, setAnalyticsList] = useState<PatientAnalytics[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

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
        const results: PatientAnalytics[] = [];
        await Promise.all(
          patientsData.map(async (p) => {
            try {
              const a = await fetchAnalytics(p.id);
              results.push(a);
            } catch {
              // skip patients without analytics
            }
          })
        );
        setAnalyticsList(results);
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
        <Skeleton className="h-64" />
      </div>
    );
  }

  // aggregate theme data across all patients
  const themeAgg: Record<string, number> = {};
  let totalThemeHits = 0;
  for (const a of analyticsList) {
    for (const td of a.themeDistribution) {
      themeAgg[td.theme] = (themeAgg[td.theme] ?? 0) + td.count;
      totalThemeHits += td.count;
    }
  }

  // conversation topics (from bias report - static categories)
  const topicData = [
    { topic: "anxiety", count: 842, pct: 24.0 },
    { topic: "depression", count: 631, pct: 18.0 },
    { topic: "relationships", count: 561, pct: 16.0 },
    { topic: "family", count: 421, pct: 12.0 },
    { topic: "work", count: 351, pct: 10.0 },
    { topic: "trauma", count: 246, pct: 7.0 },
    { topic: "grief", count: 175, pct: 5.0 },
    { topic: "identity", count: 140, pct: 4.0 },
    { topic: "substance", count: 95, pct: 2.7 },
    { topic: "self_harm", count: 50, pct: 1.4 },
  ];

  const severityData = [
    { level: "mild", count: 1580, pct: 45.0 },
    { level: "moderate", count: 1230, pct: 35.0 },
    { level: "severe", count: 520, pct: 14.8 },
    { level: "crisis", count: 92, pct: 2.6 },
    { level: "unknown", count: 90, pct: 2.6 },
  ];

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h2 className="text-lg font-semibold">Analytics & Bias Reports</h2>
        <p className="text-sm text-muted-foreground">
          Aggregated insights from the data pipeline bias detection module
        </p>
      </div>

      {/* summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Topics Tracked
            </CardTitle>
            <PieChart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">10</div>
            <p className="text-xs text-muted-foreground">
              Conversation categories
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Journal Themes
            </CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">8</div>
            <p className="text-xs text-muted-foreground">
              Tracked across all patients
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Underrepresented
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">2</div>
            <p className="text-xs text-muted-foreground">
              Topics below 3% threshold
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Sparse Patients
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {analyticsList.filter((a) => a.totalEntries < 10).length}
            </div>
            <p className="text-xs text-muted-foreground">
              Fewer than 10 entries
            </p>
          </CardContent>
        </Card>
      </div>

      {/* tabs */}
      <Tabs defaultValue="conversations">
        <TabsList>
          <TabsTrigger value="conversations">Conversation Bias</TabsTrigger>
          <TabsTrigger value="journals">Journal Bias</TabsTrigger>
          <TabsTrigger value="patients">Patient Distribution</TabsTrigger>
        </TabsList>

        {/* conversation bias */}
        <TabsContent value="conversations" className="mt-4 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* topic distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Topic Distribution</CardTitle>
                <CardDescription>
                  Classification of{" "}
                  {(stats?.totalConversations ?? 0).toLocaleString()}{" "}
                  conversations into 10 topics
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {topicData.map((t) => (
                  <DistributionBar
                    key={t.topic}
                    label={t.topic}
                    value={t.count}
                    total={stats?.totalConversations ?? 3512}
                    flagged={t.pct < 3}
                  />
                ))}
              </CardContent>
            </Card>

            {/* severity distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Severity Distribution</CardTitle>
                <CardDescription>
                  4 severity levels + unknown classification
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {severityData.map((s) => (
                  <DistributionBar
                    key={s.level}
                    label={s.level}
                    value={s.count}
                    total={stats?.totalConversations ?? 3512}
                  />
                ))}

                <div className="mt-4 rounded-lg border border-dashed p-4">
                  <p className="text-xs text-muted-foreground">
                    <AlertTriangle className="mr-1 inline h-3 w-3" />
                    Mitigation note: &quot;self_harm&quot; and
                    &quot;substance&quot; topics are underrepresented (&lt;3%).
                    Consider augmenting training data for these categories.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* journal bias */}
        <TabsContent value="journals" className="mt-4 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  Journal Theme Distribution
                </CardTitle>
                <CardDescription>
                  Aggregated across all {patients.length} patients
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {Object.entries(themeAgg)
                  .sort(([, a], [, b]) => b - a)
                  .map(([theme, count]) => (
                    <DistributionBar
                      key={theme}
                      label={theme}
                      value={count}
                      total={totalThemeHits}
                    />
                  ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Temporal Patterns</CardTitle>
                <CardDescription>
                  Entry distribution by day of week
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2.5">
                  {[
                    { day: "Monday", pct: 16 },
                    { day: "Tuesday", pct: 18 },
                    { day: "Wednesday", pct: 15 },
                    { day: "Thursday", pct: 14 },
                    { day: "Friday", pct: 12 },
                    { day: "Saturday", pct: 13 },
                    { day: "Sunday", pct: 12 },
                  ].map((d) => (
                    <DistributionBar
                      key={d.day}
                      label={d.day}
                      value={d.pct}
                      total={100}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* patient distribution */}
        <TabsContent value="patients" className="mt-4 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">
                Per-Patient Entry Distribution
              </CardTitle>
              <CardDescription>
                Patients with &lt;10 entries are flagged as sparse
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {patients.map((patient) => {
                  const a = analyticsList.find(
                    (x) => x.patientId === patient.id
                  );
                  const entries = a?.totalEntries ?? 0;
                  const maxEntries = Math.max(
                    ...analyticsList.map((x) => x.totalEntries),
                    1
                  );
                  const isSparse = entries < 10;

                  return (
                    <div key={patient.id} className="flex items-center gap-3">
                      <span className="w-36 truncate text-sm">
                        {patient.name}
                      </span>
                      <div className="flex-1">
                        <div className="h-3 overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full ${
                              isSparse
                                ? "bg-destructive/60"
                                : "bg-foreground/60"
                            }`}
                            style={{
                              width: `${(entries / maxEntries) * 100}%`,
                            }}
                          />
                        </div>
                      </div>
                      <span className="w-12 text-right text-sm font-medium">
                        {entries}
                      </span>
                      {isSparse && (
                        <Badge variant="destructive" className="text-[10px]">
                          Sparse
                        </Badge>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
