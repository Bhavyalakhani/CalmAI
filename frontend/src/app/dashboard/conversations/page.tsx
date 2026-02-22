"use client";

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
import { Search, Filter, MessageSquare, AlertTriangle } from "lucide-react";

const sampleConversations = [
  {
    id: "conv-001",
    context:
      "I've been having panic attacks almost every day. I don't know what triggers them, they just come out of nowhere and I feel like I'm dying.",
    response:
      "It sounds like you're going through a very frightening experience. Panic attacks can feel overwhelming, but it's important to know that they are not dangerous. Let's explore what might be happening in your body and mind during these episodes...",
    topic: "anxiety",
    severity: "severe",
  },
  {
    id: "conv-002",
    context:
      "My relationship with my partner has been really strained. We argue about everything and I feel like we're growing apart.",
    response:
      "Relationship conflicts can be very distressing. It takes courage to acknowledge these difficulties. Can you tell me more about what kinds of things tend to spark these arguments? Understanding the patterns might help us find ways to communicate more effectively...",
    topic: "relationships",
    severity: "moderate",
  },
  {
    id: "conv-003",
    context:
      "I recently lost my mother and I can't seem to function at work anymore. Everything reminds me of her.",
    response:
      "I'm so sorry for your loss. Grief is a deeply personal process and there's no 'right' way to experience it. The fact that everything reminds you of your mother shows the deep bond you shared. Let's talk about what you're feeling and how we can support you through this...",
    topic: "grief",
    severity: "severe",
  },
  {
    id: "conv-004",
    context:
      "I feel like I'm not good enough at my job. Everyone seems to know what they're doing except me. I'm afraid they'll find out I'm a fraud.",
    response:
      "What you're describing sounds like imposter syndrome, and it's far more common than you might think. Many high-achieving individuals experience these feelings. Let's examine the evidence — what accomplishments have you achieved in your role?",
    topic: "work",
    severity: "moderate",
  },
  {
    id: "conv-005",
    context:
      "I've been drinking more than usual to cope with stress. It started as a glass of wine at night but now I need several drinks just to relax.",
    response:
      "Thank you for being honest about this. Recognizing changes in your drinking patterns is an important first step. Alcohol can feel like it provides temporary relief, but it often amplifies the underlying issues. Let's discuss what's been causing this stress and explore healthier coping strategies...",
    topic: "substance",
    severity: "severe",
  },
];

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
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Conversation Explorer</h2>
          <p className="text-sm text-muted-foreground">
            Browse indexed therapist-patient conversations from the vector store
          </p>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search conversations..." className="pl-9" />
        </div>
        <Button variant="outline">
          <Filter className="mr-2 h-4 w-4" />
          Filter
        </Button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All Topics</TabsTrigger>
          <TabsTrigger value="anxiety">Anxiety</TabsTrigger>
          <TabsTrigger value="depression">Depression</TabsTrigger>
          <TabsTrigger value="relationships">Relationships</TabsTrigger>
          <TabsTrigger value="work">Work</TabsTrigger>
          <TabsTrigger value="grief">Grief</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4 space-y-4">
          {sampleConversations.map((conv) => (
            <Card key={conv.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm">
                    Conversation {conv.id}
                  </CardTitle>
                  <div className="flex gap-1.5">
                    <Badge
                      variant="secondary"
                      className="text-[10px] capitalize"
                    >
                      {conv.topic}
                    </Badge>
                    <Badge
                      variant={severityColor(conv.severity) as "destructive" | "secondary" | "outline"}
                      className="text-[10px] capitalize"
                    >
                      {conv.severity === "severe" && (
                        <AlertTriangle className="mr-1 h-3 w-3" />
                      )}
                      {conv.severity}
                    </Badge>
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
        </TabsContent>

        {/* Other tabs show placeholder */}
        {["anxiety", "depression", "relationships", "work", "grief"].map(
          (topic) => (
            <TabsContent key={topic} value={topic} className="mt-4">
              <Card>
                <CardContent className="flex flex-col items-center gap-2 py-16">
                  <MessageSquare className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    Filter conversations by &quot;{topic}&quot; topic
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Connected to the vector store for real-time filtering
                  </p>
                </CardContent>
              </Card>
            </TabsContent>
          )
        )}
      </Tabs>
    </div>
  );
}
