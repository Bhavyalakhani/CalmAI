"use client";

// rag assistant page - chat-style clinical assistant for therapists
// supports follow-up questions with conversation history, separated source display

import { useState, useEffect, useRef } from "react";
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
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import ReactMarkdown from "react-markdown";
import {
  Sparkles,
  BookOpen,
  MessageSquare,
  Loader2,
  Send,
  RotateCcw,
  User,
  Bot,
} from "lucide-react";
import { fetchPatients, ragSearch } from "@/lib/api";
import type { Patient, RAGResult, ConversationMessage } from "@/types";

// max follow-up turns before requiring a new conversation
const MAX_TURNS = 10;

// markdown prose styles for assistant messages
const markdownComponents = {
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

// single chat message bubble
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: RAGResult[];
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const journalSources =
    message.sources?.filter((s) => s.source === "journal") ?? [];
  const conversationSources =
    message.sources?.filter((s) => s.source === "conversation") ?? [];

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4" />
        )}
      </div>

      {/* content */}
      <div className={`max-w-[80%] space-y-3 ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block rounded-lg px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground"
          }`}
        >
          <div className="text-left">
            <ReactMarkdown components={markdownComponents}>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>

        {/* sources - only for assistant messages */}
        {!isUser && (journalSources.length > 0 || conversationSources.length > 0) && (
          <div className="space-y-2">
            {/* journal sources */}
            {journalSources.length > 0 && (
              <details className="group">
                <summary className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                  <BookOpen className="h-3 w-3" />
                  <span>{journalSources.length} journal {journalSources.length === 1 ? "entry" : "entries"}</span>
                  <Badge variant="outline" className="ml-1 text-[9px]">
                    {Math.max(...journalSources.map((s) => s.score)).toFixed(2)} top score
                  </Badge>
                </summary>
                <div className="mt-1.5 space-y-1.5 pl-4">
                  {journalSources.map((src, idx) => (
                    <div
                      key={idx}
                      className="rounded border bg-card p-2.5 text-xs"
                    >
                      <div className="mb-1 flex items-center gap-2 text-muted-foreground">
                        <BookOpen className="h-3 w-3" />
                        <span>
                          {src.metadata.entry_date || "unknown date"}
                          {src.metadata.patient_id &&
                            ` \u00B7 ${src.metadata.patient_id}`}
                        </span>
                        <Badge
                          variant="outline"
                          className="ml-auto font-mono text-[9px]"
                        >
                          {src.score.toFixed(2)}
                        </Badge>
                      </div>
                      <p className="leading-relaxed text-foreground">
                        {src.content}
                      </p>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* conversation sources */}
            {conversationSources.length > 0 && (
              <details className="group">
                <summary className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
                  <MessageSquare className="h-3 w-3" />
                  <span>{conversationSources.length} therapy {conversationSources.length === 1 ? "conversation" : "conversations"}</span>
                  <Badge variant="outline" className="ml-1 text-[9px]">
                    {Math.max(...conversationSources.map((s) => s.score)).toFixed(2)} top score
                  </Badge>
                </summary>
                <div className="mt-1.5 space-y-1.5 pl-4">
                  {conversationSources.map((src, idx) => (
                    <div
                      key={idx}
                      className="rounded border bg-card p-2.5 text-xs"
                    >
                      <div className="mb-1 flex items-center gap-2 text-muted-foreground">
                        <MessageSquare className="h-3 w-3" />
                        <span>
                          {src.metadata.conversation_id || "conversation"}
                        </span>
                        <Badge
                          variant="outline"
                          className="ml-auto font-mono text-[9px]"
                        >
                          {src.score.toFixed(2)}
                        </Badge>
                      </div>
                      <p className="leading-relaxed text-foreground">
                        {src.content}
                      </p>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function RAGAssistantPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatient, setSelectedPatient] = useState("all");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // build conversation history from messages for the api
  const conversationHistory: ConversationMessage[] = messages.map((m) => ({
    role: m.role,
    content: m.content,
  }));

  const turnCount = messages.filter((m) => m.role === "user").length;
  const canFollowUp = turnCount < MAX_TURNS;

  useEffect(() => {
    fetchPatients()
      .then(setPatients)
      .catch(() => {});
  }, []);

  // scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!query.trim() || isLoading) return;

    const userMessage = query.trim();
    setQuery("");
    setError(null);

    // add user message immediately
    const newUserMsg: ChatMessage = { role: "user", content: userMessage };
    setMessages((prev) => [...prev, newUserMsg]);
    setIsLoading(true);

    try {
      const data = await ragSearch({
        query: userMessage,
        patientId: selectedPatient !== "all" ? selectedPatient : undefined,
        topK: 5,
        conversationHistory:
          conversationHistory.length > 0 ? conversationHistory : undefined,
      });

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: data.generatedAnswer ?? "No relevant information found for this query.",
        sources: data.results,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      setError(message);
      // remove the user message on error so they can retry
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    setMessages([]);
    setError(null);
    setQuery("");
  };

  const selectedName = patients.find((p) => p.id === selectedPatient)?.name;

  return (
    <div className="space-y-4">
      {/* header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold">RAG Assistant</h2>
          <p className="text-sm text-muted-foreground">
            Clinical assistant for reviewing patient data and identifying
            patterns. All outputs are information summaries, clinical judgment
            stays with you.
          </p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleNewConversation}
            className="shrink-0"
          >
            <RotateCcw className="mr-2 h-3.5 w-3.5" />
            New Conversation
          </Button>
        )}
      </div>

      {/* patient filter */}
      <div className="flex items-end gap-4">
        <div className="space-y-1">
          <Label className="text-xs text-muted-foreground">
            Patient context
          </Label>
          <Select
            value={selectedPatient}
            onValueChange={(val) => {
              setSelectedPatient(val);
              // reset conversation when switching patients
              if (messages.length > 0) handleNewConversation();
            }}
          >
            <SelectTrigger className="h-8 w-56 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All patients</SelectItem>
              {patients.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {selectedName && (
          <p className="pb-1 text-xs text-muted-foreground">
            Searching {selectedName}&apos;s journal entries + therapy knowledge
            base
          </p>
        )}
        {!selectedName && selectedPatient === "all" && (
          <p className="pb-1 text-xs text-muted-foreground">
            Searching all patient journals + therapy knowledge base
          </p>
        )}
      </div>

      {/* chat area */}
      <Card className="flex flex-col">
        <div className="min-h-[500px] p-4" ref={scrollRef}>
          {/* empty state */}
          {messages.length === 0 && !isLoading && (
            <div className="flex h-full min-h-[400px] flex-col items-center justify-center gap-3">
              <Sparkles className="h-10 w-10 text-muted-foreground" />
              <h3 className="font-semibold">
                {selectedName
                  ? `Ask about ${selectedName}\u2019s clinical data`
                  : "Select a patient or ask a general question"}
              </h3>
              <p className="max-w-md text-center text-sm text-muted-foreground">
                Ask questions about patient journals, identify patterns, or
                explore therapy approaches from the knowledge base. Follow-up
                questions are supported.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {(selectedName
                  ? [
                      `What recurring themes appear in ${selectedName}\u2019s entries?`,
                      `Has ${selectedName} mentioned anxiety recently?`,
                      `Summarize ${selectedName}\u2019s journal progression`,
                      `Any sleep or mood concerns for ${selectedName}?`,
                    ]
                  : [
                      "What anxiety coping techniques have been discussed?",
                      "Show patterns across patients with depression themes",
                      "What therapeutic approaches work for work stress?",
                      "Summarize common sleep-related concerns",
                    ]
                ).map((suggestion) => (
                  <Button
                    key={suggestion}
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => setQuery(suggestion)}
                  >
                    {suggestion}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {/* message list */}
          {messages.length > 0 && (
            <div className="space-y-6 pb-4">
              {messages.map((msg, idx) => (
                <MessageBubble key={idx} message={msg} />
              ))}

              {/* loading indicator */}
              {isLoading && (
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-3">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">
                      Thinking...
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <Separator />

        {/* input area */}
        <div className="p-4">
          {/* error */}
          {error && (
            <div className="mb-3 rounded-lg border border-destructive/50 p-2.5">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* turn limit warning */}
          {!canFollowUp && (
            <div className="mb-3 rounded-lg border border-yellow-500/50 bg-yellow-500/10 p-2.5">
              <p className="text-sm text-yellow-600 dark:text-yellow-400">
                Conversation limit reached ({MAX_TURNS} turns). Start a new
                conversation to continue.
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <Input
              placeholder={
                !canFollowUp
                  ? "Start a new conversation to continue"
                  : messages.length > 0
                    ? "Ask a follow-up question..."
                    : selectedName
                      ? `Ask about ${selectedName}\u2019s data...`
                      : "Ask a question..."
              }
              className="flex-1"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              disabled={isLoading || !canFollowUp}
            />
            <Button
              onClick={handleSend}
              disabled={isLoading || !query.trim() || !canFollowUp}
            >
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Send
            </Button>
          </div>

          {/* status bar */}
          <div className="mt-2 flex items-center justify-between">
            <p className="text-[10px] text-muted-foreground">
              {turnCount > 0
                ? `${turnCount}/${MAX_TURNS} turns used`
                : "Information summaries only \u2014 clinical decisions are yours"}
            </p>
            {messages.length > 0 && messages.some((m) => m.role === "assistant" && (m.sources?.length ?? 0) > 0) && (
              <Badge variant="outline" className="text-[9px]">
                {messages.reduce((sum, m) => sum + (m.role === "assistant" ? (m.sources?.length ?? 0) : 0), 0)} sources referenced
              </Badge>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
