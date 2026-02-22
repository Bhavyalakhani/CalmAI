// shared mock data for frontend tests
// mirrors the shapes returned by api.ts, used across all page tests

import type {
  Therapist,
  Patient,
  JournalEntry,
  PatientAnalytics,
  DashboardStats,
  TrendDataPoint,
  Conversation,
} from "@/types";

// auth users

export const mockTherapist: Therapist = {
  id: "t-001",
  email: "sarah.chen@therapy.com",
  name: "Dr. Sarah Chen",
  role: "therapist",
  specialization: "Cognitive Behavioral Therapy",
  licenseNumber: "PSY-2024-11892",
  practiceName: "Mindful Health Practice",
  patientIds: ["p-001", "p-002", "p-003", "p-004", "p-005"],
  createdAt: "2024-01-01T00:00:00Z",
};

export const mockPatient: Patient = {
  id: "p-001",
  email: "alex.rivera@email.com",
  name: "Alex Rivera",
  role: "patient",
  therapistId: "t-001",
  dateOfBirth: "1995-03-15",
  onboardedAt: "2024-01-15T00:00:00Z",
  createdAt: "2024-01-15T00:00:00Z",
};

export const mockPatients: Patient[] = [
  mockPatient,
  {
    id: "p-002",
    email: "jordan.kim@email.com",
    name: "Jordan Kim",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1992-07-22",
    onboardedAt: "2024-02-01T00:00:00Z",
    createdAt: "2024-02-01T00:00:00Z",
  },
  {
    id: "p-003",
    email: "morgan.patel@email.com",
    name: "Morgan Patel",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1998-11-03",
    onboardedAt: "2024-02-15T00:00:00Z",
    createdAt: "2024-02-15T00:00:00Z",
  },
  {
    id: "p-004",
    email: "casey.thompson@email.com",
    name: "Casey Thompson",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1990-04-18",
    onboardedAt: "2024-03-01T00:00:00Z",
    createdAt: "2024-03-01T00:00:00Z",
  },
  {
    id: "p-005",
    email: "taylor.nguyen@email.com",
    name: "Taylor Nguyen",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1994-09-07",
    onboardedAt: "2024-03-10T00:00:00Z",
    createdAt: "2024-03-10T00:00:00Z",
  },
];

// dashboard stats

export const mockDashboardStats: DashboardStats = {
  totalPatients: 5,
  totalJournals: 196,
  totalConversations: 3512,
  avgEntriesPerPatient: 39.2,
  activePatients: 3,
};

// analytics

export const mockAnalytics: PatientAnalytics = {
  patientId: "p-001",
  totalEntries: 47,
  themeDistribution: [
    { theme: "anxiety", percentage: 35, count: 16 },
    { theme: "work", percentage: 20, count: 9 },
    { theme: "positive", percentage: 15, count: 7 },
    { theme: "sleep", percentage: 12, count: 6 },
    { theme: "social", percentage: 10, count: 5 },
    { theme: "depression", percentage: 5, count: 2 },
    { theme: "therapy", percentage: 2, count: 1 },
    { theme: "negative", percentage: 1, count: 1 },
  ],
  avgWordCount: 24,
  entryFrequency: [
    { month: "2024-11", count: 8 },
    { month: "2024-12", count: 10 },
    { month: "2025-01", count: 14 },
    { month: "2025-02", count: 15 },
  ],
  dateRange: { first: "2024-06-15", last: "2025-02-15", spanDays: 245 },
  computedAt: "2025-02-17T10:00:00Z",
};

// journal entries (5 for p-001)

export const mockJournals: JournalEntry[] = [
  {
    id: "j-001",
    patientId: "p-001",
    content:
      "I managed to get through work without feeling overwhelmed today. The breathing exercises really helped.",
    entryDate: "2025-02-15",
    themes: ["anxiety", "work", "positive"],
    wordCount: 18,
    charCount: 95,
    sentenceCount: 2,
    avgWordLength: 5.3,
    mood: 4,
    dayOfWeek: "Saturday",
    weekNumber: 7,
    month: 2,
    year: 2025,
    daysSinceLast: 3,
    isEmbedded: true,
  },
  {
    id: "j-002",
    patientId: "p-001",
    content: "Trouble sleeping again. My mind keeps racing about everything at work.",
    entryDate: "2025-02-12",
    themes: ["sleep", "anxiety", "work"],
    wordCount: 13,
    charCount: 70,
    sentenceCount: 2,
    avgWordLength: 5.4,
    mood: 2,
    dayOfWeek: "Wednesday",
    weekNumber: 7,
    month: 2,
    year: 2025,
    daysSinceLast: 2,
    isEmbedded: true,
  },
  {
    id: "j-003",
    patientId: "p-001",
    content: "Had a great chat with a friend today. Felt really connected.",
    entryDate: "2025-02-10",
    themes: ["social", "positive"],
    wordCount: 12,
    charCount: 60,
    sentenceCount: 2,
    avgWordLength: 5.0,
    mood: 5,
    dayOfWeek: "Monday",
    weekNumber: 6,
    month: 2,
    year: 2025,
    daysSinceLast: 4,
    isEmbedded: true,
  },
  {
    id: "j-004",
    patientId: "p-001",
    content: "Therapy session was really helpful. We talked about coping strategies.",
    entryDate: "2025-02-06",
    themes: ["therapy", "positive"],
    wordCount: 11,
    charCount: 68,
    sentenceCount: 2,
    avgWordLength: 6.2,
    mood: 4,
    dayOfWeek: "Thursday",
    weekNumber: 6,
    month: 2,
    year: 2025,
    daysSinceLast: 3,
    isEmbedded: true,
  },
  {
    id: "j-005",
    patientId: "p-001",
    content: "Feeling anxious about the upcoming week. Lots of deadlines.",
    entryDate: "2025-02-03",
    themes: ["anxiety", "work", "negative"],
    wordCount: 11,
    charCount: 58,
    sentenceCount: 2,
    avgWordLength: 5.3,
    mood: 2,
    dayOfWeek: "Monday",
    weekNumber: 5,
    month: 2,
    year: 2025,
    daysSinceLast: null,
    isEmbedded: true,
  },
];

// mood trend

export const mockMoodTrend: TrendDataPoint[] = [
  { date: "2025-02-09", value: 3, label: "Feb 9" },
  { date: "2025-02-10", value: 5, label: "Feb 10" },
  { date: "2025-02-11", value: 3, label: "Feb 11" },
  { date: "2025-02-12", value: 2, label: "Feb 12" },
  { date: "2025-02-13", value: 4, label: "Feb 13" },
  { date: "2025-02-14", value: 4, label: "Feb 14" },
  { date: "2025-02-15", value: 4, label: "Feb 15" },
];

// conversations

export const mockConversations: Conversation[] = [
  {
    id: "c-001",
    context:
      "I've been having panic attacks almost every day for the past two weeks. I feel like I can't breathe and my heart races.",
    response:
      "I hear you, and I want you to know that what you're experiencing is very common. Let's work through some grounding techniques together.",
    topic: "anxiety",
    severity: "severe",
    contextWordCount: 26,
    responseWordCount: 24,
    sourceFile: "dataset_1",
  },
  {
    id: "c-002",
    context:
      "My relationship with my partner has been really strained lately. We keep arguing about small things.",
    response:
      "It sounds like there's a lot of tension. Can you tell me more about what triggers these arguments?",
    topic: "relationships",
    severity: "moderate",
    contextWordCount: 17,
    responseWordCount: 18,
    sourceFile: "dataset_1",
  },
];
