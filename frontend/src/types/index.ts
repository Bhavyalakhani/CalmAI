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
  therapistName?: string;
  therapistSpecialization?: string;
  therapistLicenseNumber?: string;
}

// journal

export type MoodScore = 1 | 2 | 3 | 4 | 5; // 1 = very low, 5 = great

export interface JournalEntry {
  id: string;
  patientId: string;
  content: string;
  entryDate: string; // ISO date
  themes: string[]; // dynamic topic labels from bertopic model
  wordCount: number;
  charCount: number;
  sentenceCount: number;
  avgWordLength: number;
  mood?: MoodScore;
  promptId?: string;
  dayOfWeek: string;
  weekNumber: number;
  month: number;
  year: number;
  daysSinceLast: number | null;
  isEmbedded: boolean;
}

// conversations (therapist context)

export type SeverityLevel = "crisis" | "severe" | "moderate" | "mild" | "unknown";

export interface Conversation {
  id: string;
  context: string;
  response: string;
  topic?: string; // dynamic bertopic label
  severity?: SeverityLevel;
  contextWordCount: number;
  responseWordCount: number;
  sourceFile: string;
}

export interface TopicCount {
  label: string;
  count: number;
}

export interface SeverityCount {
  label: string;
  count: number;
}

// analytics

export interface TopicDistribution {
  topicId: number;
  label: string;
  keywords: string[];
  percentage: number;
  count: number;
}

export interface TopicOverTime {
  month: string;
  topicId: number;
  label: string;
  frequency: number;
}

export interface RepresentativeEntry {
  topicId: number;
  label: string;
  journalId: string;
  content: string;
  entryDate: string;
  probability: number;
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
  topicDistribution: TopicDistribution[];
  topicsOverTime: TopicOverTime[];
  representativeEntries: RepresentativeEntry[];
  modelVersion: string;
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

// rag assistant

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

export interface RAGQuery {
  query: string;
  patientId?: string;
  topK?: number;
  sourceType?: string;
  conversationHistory?: ConversationMessage[];
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

// therapist prompts

export type PromptStatus = "pending" | "responded";

export interface TherapistPrompt {
  promptId: string;
  therapistId: string;
  therapistName: string;
  patientId: string;
  promptText: string;
  createdAt: string;
  status: PromptStatus;
  responseJournalId?: string;
  responseContent?: string;
  respondedAt?: string;
}
