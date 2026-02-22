"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MessageSquare, Send, Calendar } from "lucide-react";

const mockPrompts = [
  {
    id: "pr-1",
    from: "Dr. Sarah Chen",
    date: "Feb 18, 2026",
    prompt:
      "This week, try writing about one moment where you noticed your anxiety and how you responded to it.",
    isAnswered: false,
  },
  {
    id: "pr-2",
    from: "Dr. Sarah Chen",
    date: "Feb 11, 2026",
    prompt:
      "Reflect on a positive interaction you had this week. What made it meaningful?",
    isAnswered: true,
    answer:
      "I had coffee with an old friend this weekend. It was meaningful because I realized I don't reach out enough. The conversation felt easy and I didn't feel the usual social anxiety.",
  },
  {
    id: "pr-3",
    from: "Dr. Sarah Chen",
    date: "Feb 4, 2026",
    prompt:
      'Write about your sleep patterns this past week. What helped or hindered your rest?',
    isAnswered: true,
    answer:
      "My sleep has been inconsistent. The nights I did breathing exercises before bed, I fell asleep faster. Work deadlines kept me up on Tuesday and Wednesday.",
  },
];

export default function PromptsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Therapist Prompts</h2>
        <p className="text-sm text-muted-foreground">
          Questions and reflection prompts from your therapist
        </p>
      </div>

      <div className="space-y-4">
        {mockPrompts.map((prompt) => (
          <Card key={prompt.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm">{prompt.from}</CardTitle>
                  <Badge
                    variant={prompt.isAnswered ? "secondary" : "outline"}
                    className="text-[10px]"
                  >
                    {prompt.isAnswered ? "Answered" : "Pending"}
                  </Badge>
                </div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  {prompt.date}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg bg-muted p-4">
                <p className="text-sm italic">&ldquo;{prompt.prompt}&rdquo;</p>
              </div>

              {prompt.isAnswered && prompt.answer ? (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    Your response
                  </p>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {prompt.answer}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <Textarea
                    placeholder="Write your response here..."
                    className="min-h-[100px] resize-none text-sm"
                  />
                  <div className="flex justify-end">
                    <Button size="sm">
                      <Send className="mr-2 h-3 w-3" />
                      Submit Response
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
