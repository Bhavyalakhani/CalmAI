// patient prompts page — view therapist-assigned reflection prompts
// pending prompts link to journal page for response, responded ones show content

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageSquare, Send, Calendar, CheckCircle2, Clock } from "lucide-react";
import { fetchPrompts } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { TherapistPrompt, Patient } from "@/types";

export default function PromptsPage() {
  const { user } = useAuth();
  const patient = user as Patient | null;
  const router = useRouter();

  const [prompts, setPrompts] = useState<TherapistPrompt[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patient?.id) return;
    fetchPrompts(patient.id)
      .then(setPrompts)
      .catch((err) => console.error("failed to load prompts:", err))
      .finally(() => setLoading(false));
  }, [patient?.id]);

  const pendingPrompts = prompts.filter((p) => p.status === "pending");
  const respondedPrompts = prompts.filter((p) => p.status === "responded");

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Therapist Prompts</h2>
        <p className="text-sm text-muted-foreground">
          Questions and reflection prompts from your therapist
        </p>
      </div>

      {/* pending prompts */}
      {pendingPrompts.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-medium">Awaiting Response</h3>
            <Badge variant="outline" className="text-[10px]">
              {pendingPrompts.length}
            </Badge>
          </div>
          {pendingPrompts.map((prompt) => (
            <Card key={prompt.promptId}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-sm">{prompt.therapistName}</CardTitle>
                    <Badge variant="outline" className="text-[10px]">
                      Pending
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Calendar className="h-3 w-3" />
                    {new Date(prompt.createdAt).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg bg-muted p-4">
                  <p className="text-sm italic">&ldquo;{prompt.promptText}&rdquo;</p>
                </div>
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    onClick={() => router.push(`/journal?promptId=${prompt.promptId}`)}
                  >
                    <Send className="mr-2 h-3 w-3" />
                    Write Response
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* responded prompts */}
      {respondedPrompts.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-medium">Responded</h3>
            <Badge variant="secondary" className="text-[10px]">
              {respondedPrompts.length}
            </Badge>
          </div>
          {respondedPrompts.map((prompt) => (
            <Card key={prompt.promptId}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-sm">{prompt.therapistName}</CardTitle>
                    <Badge variant="secondary" className="text-[10px]">
                      Answered
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Calendar className="h-3 w-3" />
                    {new Date(prompt.createdAt).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg bg-muted p-4">
                  <p className="text-sm italic">&ldquo;{prompt.promptText}&rdquo;</p>
                </div>
                {prompt.responseContent && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">
                      Your response
                      {prompt.respondedAt && (
                        <span>
                          {" · "}
                          {new Date(prompt.respondedAt).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      )}
                    </p>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {prompt.responseContent}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* empty state */}
      {prompts.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-12">
          <MessageSquare className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No prompts from your therapist yet.
          </p>
          <p className="text-xs text-muted-foreground">
            Your therapist can assign reflection prompts for you to respond to.
          </p>
        </div>
      )}
    </div>
  );
}
