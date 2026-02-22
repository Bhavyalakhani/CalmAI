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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  Sparkles,
  BookOpen,
  MessageSquare,
  ArrowRight,
  Loader2,
  FileText,
  Clock,
} from "lucide-react";
import { mockPatients } from "@/lib/mock-data";

interface MockResult {
  id: string;
  type: "journal" | "conversation";
  content: string;
  score: number;
  meta: string;
}

const mockResults: MockResult[] = [
  {
    id: "r1",
    type: "journal",
    content:
      "I've been feeling anxious about the upcoming work deadline. The breathing exercises from therapy helped me get through the meeting today without panicking.",
    score: 0.94,
    meta: "Alex Rivera · Feb 20, 2026",
  },
  {
    id: "r2",
    type: "conversation",
    content:
      "User concern: I've been having panic attacks almost every day. Counselor response: Panic attacks can feel overwhelming, but they are not dangerous. Let's explore what might be happening...",
    score: 0.91,
    meta: "Conversation conv-001 · anxiety/severe",
  },
  {
    id: "r3",
    type: "journal",
    content:
      "Practiced the grounding technique my therapist taught me. 5 things I can see, 4 I can touch. It actually worked and I calmed down within minutes.",
    score: 0.88,
    meta: "Jordan Kim · Feb 18, 2026",
  },
  {
    id: "r4",
    type: "conversation",
    content:
      "User concern: My anxiety gets worse in social situations. Counselor response: Social anxiety is very treatable. Let's start by identifying the specific situations that trigger your anxiety...",
    score: 0.85,
    meta: "Conversation conv-042 · anxiety/moderate",
  },
];

export default function RAGSearchPage() {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [results, setResults] = useState<MockResult[]>([]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setIsSearching(true);
    // simulate api call
    await new Promise((r) => setTimeout(r, 1500));
    setResults(mockResults);
    setHasSearched(true);
    setIsSearching(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold">RAG-Powered Search</h2>
        <p className="text-sm text-muted-foreground">
          Query patient journal data and conversations using natural language.
          All results are retrieved information with source citations.
        </p>
      </div>

      {/* Search Form */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Sparkles className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="e.g. What anxiety coping techniques have been discussed?"
                  className="pl-9"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                />
              </div>
              <Button onClick={handleSearch} disabled={isSearching}>
                {isSearching ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-2 h-4 w-4" />
                )}
                Search
              </Button>
            </div>

            <div className="flex gap-4">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">
                  Filter by patient
                </Label>
                <Select defaultValue="all">
                  <SelectTrigger className="h-8 w-48 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All patients</SelectItem>
                    {mockPatients.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">
                  Source type
                </Label>
                <Select defaultValue="all">
                  <SelectTrigger className="h-8 w-48 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All sources</SelectItem>
                    <SelectItem value="journal">Journals only</SelectItem>
                    <SelectItem value="conversation">
                      Conversations only
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {!hasSearched && !isSearching && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-20">
            <Sparkles className="h-10 w-10 text-muted-foreground" />
            <h3 className="font-semibold">Ask anything about your patients</h3>
            <p className="max-w-md text-center text-sm text-muted-foreground">
              Search across journals and conversations using semantic search.
              Results include relevance scores and source citations so you can
              verify every finding.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {[
                "Show anxiety patterns for Alex",
                "What sleep issues have been reported?",
                "Summarize therapy progress notes",
                "Which patients mention work stress?",
              ].map((suggestion) => (
                <Button
                  key={suggestion}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => {
                    setQuery(suggestion);
                  }}
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {isSearching && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Searching vector store...
            </p>
          </CardContent>
        </Card>
      )}

      {hasSearched && !isSearching && (
        <div className="space-y-4">
          {/* Generated Answer */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                <CardTitle className="text-sm">Generated Answer</CardTitle>
                <Badge variant="outline" className="text-[10px]">
                  Retrieved information · Not clinical advice
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed">
                Based on the retrieved journal entries and conversations,
                anxiety-related coping techniques have been a recurring topic.
                Specific techniques mentioned include breathing exercises
                (referenced by Alex Rivera, Feb 20), grounding technique — the
                5-4-3-2-1 sensory method (Jordan Kim, Feb 18), and cognitive
                restructuring discussed in counseling sessions. Multiple patients
                report these techniques as helpful in managing acute anxiety
                episodes.
              </p>
              <Separator className="my-3" />
              <p className="text-xs text-muted-foreground">
                <Clock className="mr-1 inline h-3 w-3" />
                Based on {results.length} retrieved sources · Relevance scores
                0.85–0.94
              </p>
            </CardContent>
          </Card>

          {/* Individual Results */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-muted-foreground">
              {results.length} Sources Retrieved
            </h3>
            {results.map((result) => (
              <Card key={result.id}>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        {result.type === "journal" ? (
                          <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                        ) : (
                          <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                        <span className="text-xs font-medium capitalize">
                          {result.type}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {result.meta}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed">
                        {result.content}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className="shrink-0 font-mono text-[10px]"
                    >
                      {result.score.toFixed(2)}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
