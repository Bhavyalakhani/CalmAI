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
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  LineChart,
  TrendingUp,
  TrendingDown,
  Activity,
  Brain,
} from "lucide-react";
import { fetchAnalytics } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { PatientAnalytics, Patient } from "@/types";

export default function InsightsPage() {
  const { user } = useAuth();
  const patient = user as Patient | null;
  const [analytics, setAnalytics] = useState<PatientAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patient?.id) return;
    fetchAnalytics(patient.id)
      .then(setAnalytics)
      .catch((err) => console.error("failed to load analytics:", err))
      .finally(() => setLoading(false));
  }, [patient?.id]);

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

      {/* Summary Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Entries
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
              Top Theme
            </CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">
              {analytics.themeDistribution[0]?.theme ?? "-"}
            </div>
            <p className="text-xs text-muted-foreground">
              {analytics.themeDistribution[0]?.percentage ?? 0}% of entries
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Mood Trend
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">Improving</div>
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              <TrendingUp className="h-3 w-3 text-emerald-500" />
              +0.5 avg this week
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Theme Distribution */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Theme Distribution</CardTitle>
          <CardDescription>
            Keyword-based classification of your journal entries into 8 themes
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {analytics.themeDistribution.map((td) => (
            <div key={td.theme} className="flex items-center gap-3">
              <span className="w-24 text-sm capitalize text-muted-foreground">
                {td.theme}
              </span>
              <div className="flex-1">
                <div className="h-3 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-foreground/60"
                    style={{ width: `${td.percentage}%` }}
                  />
                </div>
              </div>
              <span className="w-16 text-right text-sm font-medium">
                {td.percentage}%
              </span>
              <Badge variant="outline" className="text-[10px]">
                {td.count}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Monthly Frequency */}
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

      {/* Disclaimer */}
      <div className="rounded-lg border border-dashed p-4">
        <p className="text-xs text-muted-foreground">
          <Brain className="mr-1 inline h-3 w-3" />
          These insights are generated from keyword-based analysis of your
          journal entries. They are informational patterns, not clinical
          assessments. Please discuss any concerns with your therapist.
        </p>
      </div>
    </div>
  );
}
