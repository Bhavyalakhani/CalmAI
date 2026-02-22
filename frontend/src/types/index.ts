// calmai domain types
// auth, journals, conversations, analytics, dashboard, and rag search

// auth and users

export type UserRole = "therapist" | "patient";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  avatarUrl?: string;
  createdAt: string;
}

export interface Therapist extends User {
  role: "therapist";
  specialization: string;
  licenseNumber: string;
  practiceName?: string;
  patientIds: string[];
}

export interface Patient extends User {
  role: "patient";
  therapistId: string;
  dateOfBirth?: string;
  onboardedAt: string;
}

// journal

export type JournalTheme =
  | "anxiety"
  | "depression"
  | "positive"
  | "negative"
  | "therapy"
  | "sleep"
  | "social"
  | "work"
  | "unclassified";

export type MoodScore = 1 | 2 | 3 | 4 | 5; // 1 = very low, 5 = great

export interface JournalEntry {
  id: string;
  patientId: string;
  content: string;
  entryDate: string; // ISO date
  themes: JournalTheme[];
  wordCount: number;
  charCount: number;
  sentenceCount: number;
  avgWordLength: number;
  mood?: MoodScore;
  dayOfWeek: string;
  weekNumber: number;
  month: number;
  year: number;
  daysSinceLast: number | null;
  isEmbedded: boolean;
}

// conversations (therapist context)

export type ConversationTopic =
  | "anxiety"
  | "depression"
  | "relationships"
  | "family"
  | "work"
  | "trauma"
  | "self_harm"
  | "substance"
  | "grief"
  | "identity";

export type SeverityLevel = "crisis" | "severe" | "moderate" | "mild" | "unknown";

export interface Conversation {
  id: string;
  context: string;
  response: string;
  topic?: ConversationTopic;
  severity?: SeverityLevel;
  contextWordCount: number;
  responseWordCount: number;
  sourceFile: string;
}

// analytics

export interface ThemeDistribution {
  theme: JournalTheme;
  percentage: number;
  count: number;
}

export interface EntryFrequency {
  month: string; // "2025-01"
  count: number;
}

export interface DateRange {
  first: string;
  last: string;
  spanDays: number;
}

export interface PatientAnalytics {
  patientId: string;
  totalEntries: number;
  themeDistribution: ThemeDistribution[];
  avgWordCount: number;
  entryFrequency: EntryFrequency[];
  dateRange: DateRange | null;
  computedAt: string;
}

// dashboard view models

export interface DashboardStats {
  totalPatients: number;
  totalJournals: number;
  totalConversations: number;
  avgEntriesPerPatient: number;
  activePatients: number; // patients with entries in last 7 days
}

export interface TrendDataPoint {
  date: string;
  value: number;
  label?: string;
}

// rag / search

export interface RAGQuery {
  query: string;
  patientId?: string;
  topK?: number;
}

export interface RAGResult {
  content: string;
  score: number;
  source: "conversation" | "journal";
  metadata: Record<string, string>;
}

export interface RAGResponse {
  query: string;
  results: RAGResult[];
  generatedAnswer?: string;
  sources: string[];
}
