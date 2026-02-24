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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Search,
  Plus,
  Mail,
  Calendar,
  Activity,
  ArrowUpRight,
  Copy,
  Check,
  Loader2,
  Clock,
} from "lucide-react";
import { fetchPatients, fetchAnalytics, generateInviteCode, fetchInviteCodes } from "@/lib/api";
import type { Patient, PatientAnalytics } from "@/types";
import type { InviteCode } from "@/lib/api";

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [analyticsMap, setAnalyticsMap] = useState<Record<string, PatientAnalytics>>({});
  const [loading, setLoading] = useState(true);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [generatedCode, setGeneratedCode] = useState<string | null>(null);
  const [codeExpiry, setCodeExpiry] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [inviteCodes, setInviteCodes] = useState<InviteCode[]>([]);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const loadData = async () => {
      try {
        const patientsData = await fetchPatients();
        setPatients(patientsData);

        const analyticsResults: Record<string, PatientAnalytics> = {};
        await Promise.all(
          patientsData.map(async (p) => {
            try {
              const a = await fetchAnalytics(p.id);
              analyticsResults[p.id] = a;
            } catch {
              // analytics may not exist
            }
          })
        );
        setAnalyticsMap(analyticsResults);
      } catch (err) {
        console.error("failed to load patients:", err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const handleGenerateCode = async () => {
    setGenerating(true);
    setInviteError(null);
    try {
      const result = await generateInviteCode();
      setGeneratedCode(result.code);
      setCodeExpiry(result.expiresAt);
      // refresh invite codes list
      const codes = await fetchInviteCodes();
      setInviteCodes(codes);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate code";
      setInviteError(message);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopyCode = async () => {
    if (!generatedCode) return;
    try {
      await navigator.clipboard.writeText(generatedCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: select text
    }
  };

  const handleDialogOpen = async (open: boolean) => {
    setInviteDialogOpen(open);
    if (open) {
      // reset state and load existing codes
      setGeneratedCode(null);
      setCodeExpiry(null);
      setCopied(false);
      setInviteError(null);
      try {
        const codes = await fetchInviteCodes();
        setInviteCodes(codes);
      } catch {
        // ignore - list is supplementary
      }
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Patient Management</h2>
          <p className="text-sm text-muted-foreground">
            {patients.length} patients in your practice
          </p>
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search patients..."
              className="pl-9 w-64"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Dialog open={inviteDialogOpen} onOpenChange={handleDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Patient
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Invite a Patient</DialogTitle>
                <DialogDescription>
                  Generate a unique code and share it with your patient.
                  They&apos;ll use it during signup to link to your practice.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                {/* generate button */}
                {!generatedCode && (
                  <Button
                    onClick={handleGenerateCode}
                    disabled={generating}
                    className="w-full"
                  >
                    {generating ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      "Generate Invite Code"
                    )}
                  </Button>
                )}

                {/* error */}
                {inviteError && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {inviteError}
                  </div>
                )}

                {/* generated code display */}
                {generatedCode && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 rounded-lg border bg-muted px-4 py-3 text-center font-mono text-2xl font-bold tracking-[0.3em]">
                        {generatedCode}
                      </div>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={handleCopyCode}
                        className="h-12 w-12 shrink-0"
                      >
                        {copied ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>
                        Expires{" "}
                        {codeExpiry
                          ? new Date(codeExpiry).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })
                          : "in 7 days"}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      This code is single-use. Share it with your patient so
                      they can create their account and link to your practice.
                    </p>
                    <Separator />
                    <Button
                      variant="outline"
                      onClick={handleGenerateCode}
                      disabled={generating}
                      className="w-full"
                    >
                      Generate Another Code
                    </Button>
                  </div>
                )}

                {/* previous codes */}
                {inviteCodes.length > 0 && (
                  <div className="space-y-2">
                    <Separator />
                    <p className="text-xs font-medium text-muted-foreground">
                      Previous codes
                    </p>
                    <div className="max-h-40 space-y-1.5 overflow-y-auto">
                      {inviteCodes.map((ic) => (
                        <div
                          key={ic.code}
                          className="flex items-center justify-between rounded border px-3 py-1.5 text-xs"
                        >
                          <span className="font-mono tracking-wider">
                            {ic.code}
                          </span>
                          <Badge
                            variant={ic.isUsed ? "secondary" : "outline"}
                            className="text-[9px]"
                          >
                            {ic.isUsed ? "Used" : "Active"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* patient grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {patients.filter((p) => {
          if (!searchQuery.trim()) return true;
          const q = searchQuery.toLowerCase();
          return (
            p.name.toLowerCase().includes(q) ||
            p.email.toLowerCase().includes(q)
          );
        }).map((patient) => {
          const analytics = analyticsMap[patient.id];
          const initials = patient.name
            .split(" ")
            .map((n) => n[0])
            .join("");

          return (
            <Card key={patient.id} className="group relative">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10">
                      <AvatarFallback>{initials}</AvatarFallback>
                    </Avatar>
                    <div>
                      <CardTitle className="text-sm">{patient.name}</CardTitle>
                      <CardDescription className="text-xs">
                        ID: {patient.id}
                      </CardDescription>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100"
                    asChild
                  >
                    <Link href={`/dashboard/patients/${patient.id}`}>
                      <ArrowUpRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Mail className="h-3 w-3" />
                  <span>{patient.email}</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  <span>
                    Onboarded{" "}
                    {new Date(patient.onboardedAt).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </span>
                </div>

                <Separator />

                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Processed Entries</span>
                  <span className="font-medium">
                    {analytics?.totalEntries ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Avg words</span>
                  <span className="font-medium">
                    {analytics?.avgWordCount ?? "-"}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Top topic</span>
                  <Badge
                    variant="secondary"
                    className="text-[10px] capitalize"
                  >
                    <Activity className="mr-1 h-3 w-3" />
                    {analytics?.topicDistribution[0]?.label ?? "-"}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
