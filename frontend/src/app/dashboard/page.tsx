"use client";

import { useState } from "react";
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
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
} from "lucide-react";
import {
  mockPatients,
  mockDashboardStats,
  mockPatientAnalytics,
  mockJournalEntries,
  mockMoodTrend,
  getAnalyticsForPatient,
  getJournalsForPatient,
} from "@/lib/mock-data";
import type { Patient, JournalEntry } from "@/types";

/* stat card */

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

/* mini mood sparkline (text-based chart) */

function MoodSparkline() {
  const moods = mockMoodTrend;
  const max = 5;

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

/* theme bar */

function ThemeBar({
  theme,
  percentage,
}: {
  theme: string;
  percentage: number;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 text-sm capitalize text-muted-foreground">
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

/* journal timeline item */

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

/* patient list item */

function PatientItem({
  patient,
  isSelected,
  onClick,
}: {
  patient: Patient;
  isSelected: boolean;
  onClick: () => void;
}) {
  const analytics = getAnalyticsForPatient(patient.id);
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
      {analytics && analytics.totalEntries > 0 && (
        <Badge variant="outline" className="text-[10px]">
          <Activity className="mr-1 h-3 w-3" />
          {analytics.themeDistribution[0]?.theme}
        </Badge>
      )}
    </button>
  );
}

/* rag search placeholder */

function RAGSearchPanel() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          <CardTitle className="text-sm font-medium">RAG Assistant</CardTitle>
        </div>
        <CardDescription>
          Ask questions about your patients&apos; journal data
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          <Input
            placeholder="e.g. What themes appear in Alex's recent entries?"
            className="flex-1"
          />
          <Button size="icon" variant="outline">
            <Search className="h-4 w-4" />
          </Button>
        </div>
        <div className="mt-4 rounded-lg border border-dashed p-8 text-center">
          <p className="text-sm text-muted-foreground">
            RAG-powered responses will appear here with source citations.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            All answers are retrieved information — clinical judgment stays with
            you.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

/* main dashboard page */

export default function DashboardOverview() {
  const [selectedPatientId, setSelectedPatientId] = useState<string>(
    mockPatients[0]?.id ?? ""
  );

  const selectedAnalytics = getAnalyticsForPatient(selectedPatientId);
  const selectedJournals = getJournalsForPatient(selectedPatientId);
  const selectedPatient = mockPatients.find(
    (p) => p.id === selectedPatientId
  );

  return (
    <div className="space-y-6">
      {/* stats row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Patients"
          value={mockDashboardStats.totalPatients.toString()}
          description="+2 this month"
          icon={Users}
          trend="up"
        />
        <StatCard
          title="Journal Entries"
          value={mockDashboardStats.totalJournals.toString()}
          description="+18 this week"
          icon={BookOpen}
          trend="up"
        />
        <StatCard
          title="Conversations"
          value={mockDashboardStats.totalConversations.toLocaleString()}
          description="Indexed in vector store"
          icon={MessageSquare}
        />
        <StatCard
          title="Active Patients"
          value={`${mockDashboardStats.activePatients}/${mockDashboardStats.totalPatients}`}
          description="Entries in last 7 days"
          icon={Activity}
          trend="up"
        />
      </div>

      {/* main grid */}
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* patient list */}
        <Card className="lg:row-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Patients</CardTitle>
            <CardDescription>
              {mockPatients.length} active patients
            </CardDescription>
          </CardHeader>
          <CardContent className="px-2">
            <ScrollArea className="h-[540px]">
              <div className="space-y-0.5 px-1">
                {mockPatients.map((patient) => (
                  <PatientItem
                    key={patient.id}
                    patient={patient}
                    isSelected={patient.id === selectedPatientId}
                    onClick={() => setSelectedPatientId(patient.id)}
                  />
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* right column */}
        <div className="space-y-6">
          {/* Patient Analytics */}
          {selectedPatient && selectedAnalytics && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-medium">
                      {selectedPatient.name} — Analytics
                    </CardTitle>
                    <CardDescription>
                      {selectedAnalytics.totalEntries} entries over{" "}
                      {selectedAnalytics.dateRange?.spanDays ?? 0} days
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm">
                    View Full Profile
                    <ArrowRight className="ml-1 h-3 w-3" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-6 sm:grid-cols-2">
                  {/* Theme Distribution */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Theme Distribution
                    </h4>
                    <div className="space-y-2">
                      {selectedAnalytics.themeDistribution
                        .slice(0, 6)
                        .map((t) => (
                          <ThemeBar
                            key={t.theme}
                            theme={t.theme}
                            percentage={t.percentage}
                          />
                        ))}
                    </div>
                  </div>

                  {/* Quick Stats */}
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
                          {selectedAnalytics.dateRange?.spanDays ?? "—"}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          Span (days)
                        </div>
                      </div>
                      <div className="rounded-lg border p-3 text-center">
                        <div className="text-lg font-bold capitalize">
                          {selectedAnalytics.themeDistribution[0]?.theme ??
                            "—"}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          Top theme
                        </div>
                      </div>
                    </div>

                    {/* Entry Frequency */}
                    <div>
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

          {/* Mood Sparkline */}
          <MoodSparkline />

          {/* RAG Search */}
          <RAGSearchPanel />
        </div>
      </div>

      {/* recent timeline */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-sm font-medium">
              Recent Journal Entries —{" "}
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
