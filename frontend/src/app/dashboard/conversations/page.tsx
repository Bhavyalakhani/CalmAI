"use client";

// conversation explorer — keyword search, topic/severity dropdown filters, pagination

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Search,
  MessageSquare,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  X,
  SlidersHorizontal,
} from "lucide-react";
import {
  fetchConversations,
  fetchConversationTopics,
  fetchConversationSeverities,
} from "@/lib/api";
import type { Conversation } from "@/types";

const PAGE_SIZE = 10;

function severityColor(severity: string) {
  switch (severity) {
    case "crisis":
    case "severe":
      return "destructive";
    case "moderate":
      return "secondary";
    default:
      return "outline" as const;
  }
}

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

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // search + filters
  const [searchInput, setSearchInput] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("all");
  const [selectedSeverity, setSelectedSeverity] = useState("all");
  const [page, setPage] = useState(1);

  // dynamic filter options from api
  const [topicOptions, setTopicOptions] = useState<
    { label: string; count: number }[]
  >([]);
  const [severityOptions, setSeverityOptions] = useState<
    { label: string; count: number }[]
  >([]);

  // load filter options on mount
  useEffect(() => {
    fetchConversationTopics()
      .then((data) => setTopicOptions(data.topics ?? []))
      .catch(() => setTopicOptions([]));
    fetchConversationSeverities()
      .then((data) => setSeverityOptions(data.severities ?? []))
      .catch(() => setSeverityOptions([]));
  }, []);

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const params: {
        topic?: string;
        severity?: string;
        search?: string;
        page: number;
        pageSize: number;
      } = { page, pageSize: PAGE_SIZE };

      if (selectedTopic !== "all") params.topic = selectedTopic;
      if (selectedSeverity !== "all") params.severity = selectedSeverity;
      if (activeSearch.trim()) params.search = activeSearch.trim();

      const data = await fetchConversations(params);
      setConversations(data.conversations);
      setTotal(data.total);
    } catch (err) {
      console.error("failed to load conversations:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedTopic, selectedSeverity, activeSearch, page]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSearch = () => {
    setActiveSearch(searchInput);
    setPage(1);
  };

  const clearFilters = () => {
    setSearchInput("");
    setActiveSearch("");
    setSelectedTopic("all");
    setSelectedSeverity("all");
    setPage(1);
  };

  const hasFilters =
    activeSearch || selectedTopic !== "all" || selectedSeverity !== "all";
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      {/* header */}
      <div>
        <h2 className="text-lg font-semibold">Conversation Explorer</h2>
        <p className="text-sm text-muted-foreground">
          Search and filter {total.toLocaleString()} indexed therapist-patient
          conversations from 2 publicly available datasets.
        </p>
      </div>

      {/* search and filters */}
      <Card>
        <CardContent className="pt-6">
          {/* keyword search row */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by keyword (e.g. anxiety, relationship, coping)..."
                className="pl-9"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button onClick={handleSearch}>
              <Search className="mr-2 h-4 w-4" />
              Search
            </Button>
          </div>

          <Separator className="my-4" />

          {/* filter row */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <SlidersHorizontal className="h-4 w-4" />
              Filters
            </div>

            {/* topic dropdown */}
            <Select
              value={selectedTopic}
              onValueChange={(v) => {
                setSelectedTopic(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-[260px]">
                <SelectValue placeholder="All Topics" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Topics</SelectItem>
                {topicOptions.map((t) => (
                  <SelectItem key={t.label} value={t.label}>
                    <span className="truncate">{t.label}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      ({t.count})
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* severity dropdown */}
            <Select
              value={selectedSeverity}
              onValueChange={(v) => {
                setSelectedSeverity(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Severities" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                {severityOptions.map((s) => (
                  <SelectItem key={s.label} value={s.label}>
                    <div className="flex items-center gap-2">
                      <div
                        className={`h-2 w-2 rounded-full ${severityDot(s.label)}`}
                      />
                      <span className="capitalize">{s.label}</span>
                      <span className="text-xs text-muted-foreground">
                        ({s.count})
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* clear filters */}
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="mr-1 h-3 w-3" />
                Clear filters
              </Button>
            )}
          </div>

          {/* active filter chips */}
          {hasFilters && (
            <div className="mt-3 flex flex-wrap gap-2">
              {activeSearch && (
                <Badge variant="secondary" className="gap-1">
                  Search: &quot;{activeSearch}&quot;
                  <button
                    onClick={() => {
                      setSearchInput("");
                      setActiveSearch("");
                      setPage(1);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              )}
              {selectedTopic !== "all" && (
                <Badge variant="secondary" className="gap-1">
                  Topic: {selectedTopic}
                  <button
                    onClick={() => {
                      setSelectedTopic("all");
                      setPage(1);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              )}
              {selectedSeverity !== "all" && (
                <Badge variant="secondary" className="gap-1 capitalize">
                  Severity: {selectedSeverity}
                  <button
                    onClick={() => {
                      setSelectedSeverity("all");
                      setPage(1);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* results */}
      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
      ) : conversations.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16">
            <MessageSquare className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm font-medium">No conversations found</p>
            <p className="text-xs text-muted-foreground">
              Try adjusting your search or filters
            </p>
            {hasFilters && (
              <Button variant="outline" size="sm" onClick={clearFilters}>
                Clear all filters
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          {/* result count */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {(page - 1) * PAGE_SIZE + 1}–
              {Math.min(page * PAGE_SIZE, total)} of{" "}
              {total.toLocaleString()} results
            </p>
          </div>

          {/* conversation cards */}
          <div className="space-y-3">
            {conversations.map((conv) => (
              <Card
                key={conv.id}
                className="transition-colors hover:border-foreground/20"
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <CardTitle className="text-sm font-medium">
                        #{conv.id.slice(0, 8)}
                      </CardTitle>
                    </div>
                    <div className="flex flex-wrap shrink-0 gap-1.5">
                      {conv.topic && (
                        <Badge
                          variant="secondary"
                          className="text-[10px]"
                        >
                          {conv.topic}
                        </Badge>
                      )}
                      {conv.severity && conv.severity !== "unknown" && (
                        <Badge
                          variant={
                            severityColor(conv.severity) as
                              | "destructive"
                              | "secondary"
                              | "outline"
                          }
                          className="text-[10px] capitalize gap-1"
                        >
                          {(conv.severity === "crisis" ||
                            conv.severity === "severe") && (
                            <AlertTriangle className="h-3 w-3" />
                          )}
                          {conv.severity}
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="rounded-lg bg-muted/50 p-3">
                    <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      Patient
                    </p>
                    <p className="text-sm leading-relaxed">{conv.context}</p>
                  </div>
                  <div className="rounded-lg border border-dashed p-3">
                    <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      Counselor
                    </p>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {conv.response}
                    </p>
                  </div>
                  {/* meta */}
                  <div className="flex gap-4 text-[10px] text-muted-foreground">
                    <span>Patient: {conv.contextWordCount} words</span>
                    <span>Counselor: {conv.responseWordCount} words</span>
                    <span>Source: {conv.sourceFile}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* pagination */}
          <div className="flex items-center justify-between pt-2">
            <p className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
