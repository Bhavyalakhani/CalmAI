import {
  Patient,
  Therapist,
  JournalEntry,
  PatientAnalytics,
  DashboardStats,
  TrendDataPoint,
} from "@/types";

// mock data powering all frontend views
// therapist, patients, journals, analytics, dashboard stats, and mood trend

// mock therapist

export const mockTherapist: Therapist = {
  id: "t-001",
  email: "dr.chen@calmai.com",
  name: "Dr. Sarah Chen",
  role: "therapist",
  specialization: "Cognitive Behavioral Therapy",
  licenseNumber: "PSY-2024-11892",
  practiceName: "Mindful Path Clinic",
  patientIds: ["p-001", "p-002", "p-003", "p-004", "p-005"],
  avatarUrl: "",
  createdAt: "2024-06-15T00:00:00Z",
};

// mock patients

export const mockPatients: Patient[] = [
  {
    id: "p-001",
    email: "alex.rivera@email.com",
    name: "Alex Rivera",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1995-03-12",
    onboardedAt: "2025-01-10T00:00:00Z",
    createdAt: "2025-01-10T00:00:00Z",
  },
  {
    id: "p-002",
    email: "jordan.kim@email.com",
    name: "Jordan Kim",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1990-08-25",
    onboardedAt: "2025-02-01T00:00:00Z",
    createdAt: "2025-02-01T00:00:00Z",
  },
  {
    id: "p-003",
    email: "morgan.patel@email.com",
    name: "Morgan Patel",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1988-11-03",
    onboardedAt: "2024-11-20T00:00:00Z",
    createdAt: "2024-11-20T00:00:00Z",
  },
  {
    id: "p-004",
    email: "casey.thompson@email.com",
    name: "Casey Thompson",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1998-05-17",
    onboardedAt: "2025-03-05T00:00:00Z",
    createdAt: "2025-03-05T00:00:00Z",
  },
  {
    id: "p-005",
    email: "taylor.nguyen@email.com",
    name: "Taylor Nguyen",
    role: "patient",
    therapistId: "t-001",
    dateOfBirth: "1992-09-30",
    onboardedAt: "2024-12-15T00:00:00Z",
    createdAt: "2024-12-15T00:00:00Z",
  },
];

// mock journal entries

export const mockJournalEntries: JournalEntry[] = [
  {
    id: "j-001",
    patientId: "p-001",
    content:
      "Today was a good day. I managed to get through work without feeling overwhelmed. The breathing exercises from therapy really helped when I felt anxious during the meeting.",
    entryDate: "2026-02-20T00:00:00Z",
    themes: ["anxiety", "positive", "therapy"],
    wordCount: 30,
    charCount: 172,
    sentenceCount: 3,
    avgWordLength: 4.8,
    mood: 4,
    dayOfWeek: "Thursday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 2,
    isEmbedded: true,
  },
  {
    id: "j-002",
    patientId: "p-001",
    content:
      "I couldn't sleep last night. My mind kept racing about the upcoming deadline at work. I feel exhausted and irritated today. Tried journaling before bed but it didn't help.",
    entryDate: "2026-02-18T00:00:00Z",
    themes: ["sleep", "work", "negative"],
    wordCount: 32,
    charCount: 168,
    sentenceCount: 4,
    avgWordLength: 4.3,
    mood: 2,
    dayOfWeek: "Tuesday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 3,
    isEmbedded: true,
  },
  {
    id: "j-003",
    patientId: "p-001",
    content:
      "Had a great session with Dr. Chen today. We talked about cognitive distortions and I'm starting to recognize when I catastrophize. Feeling hopeful about the progress.",
    entryDate: "2026-02-15T00:00:00Z",
    themes: ["therapy", "positive"],
    wordCount: 28,
    charCount: 164,
    sentenceCount: 3,
    avgWordLength: 5.1,
    mood: 4,
    dayOfWeek: "Saturday",
    weekNumber: 7,
    month: 2,
    year: 2026,
    daysSinceLast: 1,
    isEmbedded: true,
  },
  {
    id: "j-004",
    patientId: "p-001",
    content:
      "Feeling really down today. I had an argument with my partner about finances. I isolated myself in the bedroom for hours. I know this isn't healthy but I didn't know what else to do.",
    entryDate: "2026-02-14T00:00:00Z",
    themes: ["depression", "negative", "social"],
    wordCount: 35,
    charCount: 178,
    sentenceCount: 4,
    avgWordLength: 4.1,
    mood: 1,
    dayOfWeek: "Friday",
    weekNumber: 7,
    month: 2,
    year: 2026,
    daysSinceLast: 2,
    isEmbedded: true,
  },
  {
    id: "j-005",
    patientId: "p-001",
    content:
      "Went for a walk in the park after work. The fresh air felt amazing. I noticed I wasn't worrying about anything for the first time in weeks. Small wins matter.",
    entryDate: "2026-02-12T00:00:00Z",
    themes: ["positive"],
    wordCount: 29,
    charCount: 152,
    sentenceCount: 4,
    avgWordLength: 4.2,
    mood: 5,
    dayOfWeek: "Wednesday",
    weekNumber: 7,
    month: 2,
    year: 2026,
    daysSinceLast: 4,
    isEmbedded: true,
  },
  {
    id: "j-006",
    patientId: "p-002",
    content:
      "My anxiety was really bad today. I had a panic attack at the grocery store and had to leave without buying anything. I feel embarrassed and frustrated.",
    entryDate: "2026-02-19T00:00:00Z",
    themes: ["anxiety", "negative"],
    wordCount: 28,
    charCount: 148,
    sentenceCount: 3,
    avgWordLength: 4.5,
    mood: 1,
    dayOfWeek: "Wednesday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 1,
    isEmbedded: true,
  },
  {
    id: "j-007",
    patientId: "p-002",
    content:
      "Practiced the grounding technique my therapist taught me. 5 things I can see, 4 I can touch, 3 I can hear. It actually worked and I calmed down within minutes.",
    entryDate: "2026-02-18T00:00:00Z",
    themes: ["therapy", "positive", "anxiety"],
    wordCount: 30,
    charCount: 156,
    sentenceCount: 3,
    avgWordLength: 4.0,
    mood: 3,
    dayOfWeek: "Tuesday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 3,
    isEmbedded: true,
  },
  {
    id: "j-008",
    patientId: "p-003",
    content:
      "Work has been incredibly stressful. My boss assigned me three new projects and I don't know how to say no. I feel overwhelmed and my sleep is suffering.",
    entryDate: "2026-02-20T00:00:00Z",
    themes: ["work", "anxiety", "sleep"],
    wordCount: 28,
    charCount: 150,
    sentenceCount: 3,
    avgWordLength: 4.4,
    mood: 2,
    dayOfWeek: "Thursday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 2,
    isEmbedded: true,
  },
  {
    id: "j-009",
    patientId: "p-004",
    content:
      "I'm grateful today. Had coffee with an old friend and we talked for hours. It reminded me that I have people who care about me. Need to do this more often.",
    entryDate: "2026-02-19T00:00:00Z",
    themes: ["positive", "social"],
    wordCount: 29,
    charCount: 153,
    sentenceCount: 4,
    avgWordLength: 4.0,
    mood: 5,
    dayOfWeek: "Wednesday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 5,
    isEmbedded: true,
  },
  {
    id: "j-010",
    patientId: "p-005",
    content:
      "Therapy today was tough. We discussed my childhood and I cried a lot. I feel drained but also lighter somehow. The process is painful but necessary.",
    entryDate: "2026-02-20T00:00:00Z",
    themes: ["therapy", "depression"],
    wordCount: 27,
    charCount: 147,
    sentenceCount: 4,
    avgWordLength: 4.5,
    mood: 3,
    dayOfWeek: "Thursday",
    weekNumber: 8,
    month: 2,
    year: 2026,
    daysSinceLast: 3,
    isEmbedded: true,
  },
];

// mock analytics

export const mockPatientAnalytics: PatientAnalytics[] = [
  {
    patientId: "p-001",
    totalEntries: 47,
    themeDistribution: [
      { theme: "anxiety", percentage: 28.5, count: 22 },
      { theme: "positive", percentage: 19.4, count: 15 },
      { theme: "therapy", percentage: 15.2, count: 12 },
      { theme: "work", percentage: 12.1, count: 9 },
      { theme: "sleep", percentage: 8.8, count: 7 },
      { theme: "depression", percentage: 7.0, count: 5 },
      { theme: "social", percentage: 5.5, count: 4 },
      { theme: "negative", percentage: 3.5, count: 3 },
    ],
    avgWordCount: 28.4,
    entryFrequency: [
      { month: "2025-10", count: 8 },
      { month: "2025-11", count: 10 },
      { month: "2025-12", count: 9 },
      { month: "2026-01", count: 12 },
      { month: "2026-02", count: 8 },
    ],
    dateRange: { first: "2025-10-01", last: "2026-02-20", spanDays: 143 },
    computedAt: "2026-02-20T12:00:00Z",
  },
  {
    patientId: "p-002",
    totalEntries: 32,
    themeDistribution: [
      { theme: "anxiety", percentage: 38.2, count: 26 },
      { theme: "therapy", percentage: 18.0, count: 12 },
      { theme: "positive", percentage: 14.5, count: 10 },
      { theme: "negative", percentage: 11.3, count: 8 },
      { theme: "social", percentage: 8.5, count: 6 },
      { theme: "sleep", percentage: 5.0, count: 3 },
      { theme: "work", percentage: 4.5, count: 3 },
    ],
    avgWordCount: 25.1,
    entryFrequency: [
      { month: "2025-11", count: 5 },
      { month: "2025-12", count: 8 },
      { month: "2026-01", count: 11 },
      { month: "2026-02", count: 8 },
    ],
    dateRange: { first: "2025-11-05", last: "2026-02-19", spanDays: 106 },
    computedAt: "2026-02-20T12:00:00Z",
  },
  {
    patientId: "p-003",
    totalEntries: 58,
    themeDistribution: [
      { theme: "work", percentage: 32.0, count: 30 },
      { theme: "anxiety", percentage: 22.1, count: 21 },
      { theme: "sleep", percentage: 16.4, count: 15 },
      { theme: "negative", percentage: 10.5, count: 10 },
      { theme: "therapy", percentage: 9.0, count: 8 },
      { theme: "positive", percentage: 6.5, count: 6 },
      { theme: "social", percentage: 3.5, count: 3 },
    ],
    avgWordCount: 31.2,
    entryFrequency: [
      { month: "2025-09", count: 10 },
      { month: "2025-10", count: 12 },
      { month: "2025-11", count: 11 },
      { month: "2025-12", count: 9 },
      { month: "2026-01", count: 10 },
      { month: "2026-02", count: 6 },
    ],
    dateRange: { first: "2025-09-15", last: "2026-02-20", spanDays: 158 },
    computedAt: "2026-02-20T12:00:00Z",
  },
  {
    patientId: "p-004",
    totalEntries: 18,
    themeDistribution: [
      { theme: "positive", percentage: 30.0, count: 9 },
      { theme: "social", percentage: 25.0, count: 8 },
      { theme: "therapy", percentage: 18.0, count: 5 },
      { theme: "anxiety", percentage: 12.0, count: 4 },
      { theme: "work", percentage: 8.0, count: 2 },
      { theme: "negative", percentage: 7.0, count: 2 },
    ],
    avgWordCount: 26.8,
    entryFrequency: [
      { month: "2025-12", count: 4 },
      { month: "2026-01", count: 7 },
      { month: "2026-02", count: 7 },
    ],
    dateRange: { first: "2025-12-10", last: "2026-02-19", spanDays: 71 },
    computedAt: "2026-02-20T12:00:00Z",
  },
  {
    patientId: "p-005",
    totalEntries: 41,
    themeDistribution: [
      { theme: "depression", percentage: 25.3, count: 18 },
      { theme: "therapy", percentage: 22.0, count: 16 },
      { theme: "anxiety", percentage: 15.8, count: 11 },
      { theme: "negative", percentage: 13.0, count: 9 },
      { theme: "positive", percentage: 10.5, count: 8 },
      { theme: "sleep", percentage: 7.2, count: 5 },
      { theme: "social", percentage: 6.2, count: 4 },
    ],
    avgWordCount: 29.5,
    entryFrequency: [
      { month: "2025-10", count: 6 },
      { month: "2025-11", count: 9 },
      { month: "2025-12", count: 8 },
      { month: "2026-01", count: 10 },
      { month: "2026-02", count: 8 },
    ],
    dateRange: { first: "2025-10-20", last: "2026-02-20", spanDays: 123 },
    computedAt: "2026-02-20T12:00:00Z",
  },
];

// mock dashboard stats

export const mockDashboardStats: DashboardStats = {
  totalPatients: 5,
  totalJournals: 196,
  totalConversations: 3512,
  avgEntriesPerPatient: 39.2,
  activePatients: 4,
};

// mock mood trend data

export const mockMoodTrend: TrendDataPoint[] = [
  { date: "2026-02-08", value: 3, label: "Moderate" },
  { date: "2026-02-09", value: 2, label: "Low" },
  { date: "2026-02-10", value: 2, label: "Low" },
  { date: "2026-02-11", value: 3, label: "Moderate" },
  { date: "2026-02-12", value: 5, label: "Great" },
  { date: "2026-02-13", value: 4, label: "Good" },
  { date: "2026-02-14", value: 1, label: "Very Low" },
  { date: "2026-02-15", value: 4, label: "Good" },
  { date: "2026-02-16", value: 3, label: "Moderate" },
  { date: "2026-02-17", value: 3, label: "Moderate" },
  { date: "2026-02-18", value: 2, label: "Low" },
  { date: "2026-02-19", value: 3, label: "Moderate" },
  { date: "2026-02-20", value: 4, label: "Good" },
];

// helpers

export function getPatientById(id: string): Patient | undefined {
  return mockPatients.find((p) => p.id === id);
}

export function getAnalyticsForPatient(
  patientId: string
): PatientAnalytics | undefined {
  return mockPatientAnalytics.find((a) => a.patientId === patientId);
}

export function getJournalsForPatient(patientId: string): JournalEntry[] {
  return mockJournalEntries
    .filter((j) => j.patientId === patientId)
    .sort(
      (a, b) =>
        new Date(b.entryDate).getTime() - new Date(a.entryDate).getTime()
    );
}
