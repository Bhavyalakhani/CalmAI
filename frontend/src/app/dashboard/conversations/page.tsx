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
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, Filter, MessageSquare, AlertTriangle, Loader2 } from "lucide-react";
import { fetchConversations } from "@/lib/api";
import type { Conversation } from "@/types";

function severityColor(severity: string) {
  switch (severity) {
    case "crisis":
      return "destructive";
    case "severe":
      return "destructive";
    case "moderate":
      return "secondary";
    case "mild":
      return "outline";
    default:
      return "outline" as const;
  }
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTopic, setActiveTopic] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const params: { topic?: string; search?: string; page: number; pageSize: number } = {
        page,
        pageSize,
      };
      if (activeTopic !== "all") params.topic = activeTopic;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const data = await fetchConversations(params);
      setConversations(data.conversations);
      setTotal(data.total);
    } catch (err) {
      console.error("failed to load conversations:", err);
    } finally {
      setLoading(false);
    }
  }, [activeTopic, searchQuery, page]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSearch = () => {
    setPage(1);
    loadConversations();
  };

  const handleTopicChange = (topic: string) => {
    setActiveTopic(topic);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Conversation Explorer</h2>
          <p className="text-sm text-muted-foreground">
            Browse {total.toLocaleString()} indexed therapist-patient conversations from the vector store
          </p>
        </div>
      </div>

      {/* search & filter */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search conversations..."
            className="pl-9"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Button variant="outline" onClick={handleSearch}>
          <Filter className="mr-2 h-4 w-4" />
          Filter
        </Button>
      </div>

      {/* tabs */}
      <Tabs value={activeTopic} onValueChange={handleTopicChange}>
        <TabsList>
          <TabsTrigger value="all">All Topics</TabsTrigger>
          <TabsTrigger value="anxiety">Anxiety</TabsTrigger>
          <TabsTrigger value="depression">Depression</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
          <TabsTrigger value="work">Work</TabsTrigger>
          <TabsTrigger value="grief">Grief</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTopic} className="mt-4 space-y-4">
          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          ) : conversations.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-16">
                <MessageSquare className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  No conversations found for this filter.
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              {conversations.map((conv) => (
                <Card key={conv.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 text-muted-foreground" />
                      <CardTitle className="text-sm">
                        Conversation {conv.id.slice(0, 8)}
                      </CardTitle>
                      <div className="flex gap-1.5">
                        {conv.topic && (
                          <Badge
                            variant="secondary"
                            className="text-[10px] capitalize"
                          >
                            {conv.topic}
                          </Badge>
                        )}
                        {conv.severity && (
                          <Badge
                            variant={
                              severityColor(conv.severity) as
                                | "destructive"
                                | "secondary"
                                | "outline"
                            }
                            className="text-[10px] capitalize"
                          >
                            {conv.severity === "severe" && (
                              <AlertTriangle className="mr-1 h-3 w-3" />
                            )}
                            {conv.severity}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div>
                      <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Patient Context
                      </p>
                      <p className="text-sm leading-relaxed">{conv.context}</p>
                    </div>
                    <div>
                      <p className="mb-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Counselor Response
                      </p>
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        {conv.response}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))}

              {/* pagination */}
              <div className="flex items-center justify-between pt-2">
                <p className="text-sm text-muted-foreground">
                  Page {page} · Showing {conversations.length} of{" "}
                  {total.toLocaleString()}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page * pageSize >= total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
