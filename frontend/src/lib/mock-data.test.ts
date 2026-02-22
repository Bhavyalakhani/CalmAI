import { describe, it, expect } from "vitest";
import {
  mockTherapist,
  mockPatients,
  mockJournalEntries,
  mockPatientAnalytics,
  mockDashboardStats,
  mockMoodTrend,
  getPatientById,
  getAnalyticsForPatient,
  getJournalsForPatient,
} from "@/lib/mock-data";

// data shape tests

describe("mock data exports", () => {
  it("exports a therapist with valid structure", () => {
    expect(mockTherapist).toBeDefined();
    expect(mockTherapist.role).toBe("therapist");
    expect(mockTherapist.patientIds).toHaveLength(5);
    expect(mockTherapist.licenseNumber).toBeTruthy();
    expect(mockTherapist.specialization).toBeTruthy();
  });

  it("exports 5 mock patients", () => {
    expect(mockPatients).toHaveLength(5);
    mockPatients.forEach((p) => {
      expect(p.role).toBe("patient");
      expect(p.therapistId).toBe("t-001");
      expect(p.id).toMatch(/^p-\d{3}$/);
    });
  });

  it("exports 10 journal entries with required fields", () => {
    expect(mockJournalEntries).toHaveLength(10);
    mockJournalEntries.forEach((j) => {
      expect(j.id).toBeTruthy();
      expect(j.patientId).toBeTruthy();
      expect(j.content).toBeTruthy();
      expect(j.entryDate).toBeTruthy();
      expect(j.themes.length).toBeGreaterThan(0);
      expect(j.wordCount).toBeGreaterThan(0);
      expect(j.isEmbedded).toBe(true);
    });
  });

  it("exports 5 patient analytics records", () => {
    expect(mockPatientAnalytics).toHaveLength(5);
    mockPatientAnalytics.forEach((a) => {
      expect(a.patientId).toBeTruthy();
      expect(a.totalEntries).toBeGreaterThan(0);
      expect(a.themeDistribution.length).toBeGreaterThan(0);
      expect(a.avgWordCount).toBeGreaterThan(0);
      expect(a.entryFrequency.length).toBeGreaterThan(0);
    });
  });

  it("exports dashboard stats with all fields", () => {
    expect(mockDashboardStats.totalPatients).toBe(5);
    expect(mockDashboardStats.totalJournals).toBeGreaterThan(0);
    expect(mockDashboardStats.totalConversations).toBeGreaterThan(0);
    expect(mockDashboardStats.avgEntriesPerPatient).toBeGreaterThan(0);
    expect(mockDashboardStats.activePatients).toBeGreaterThanOrEqual(0);
  });

  it("exports mood trend data points", () => {
    expect(mockMoodTrend.length).toBeGreaterThan(0);
    mockMoodTrend.forEach((point) => {
      expect(point.date).toBeTruthy();
      expect(point.value).toBeGreaterThanOrEqual(1);
      expect(point.value).toBeLessThanOrEqual(5);
    });
  });

  it("patient IDs in therapist.patientIds match patients", () => {
    const patientIds = mockPatients.map((p) => p.id);
    mockTherapist.patientIds.forEach((id) => {
      expect(patientIds).toContain(id);
    });
  });

  it("journal entries reference valid patient IDs", () => {
    const patientIds = mockPatients.map((p) => p.id);
    mockJournalEntries.forEach((j) => {
      expect(patientIds).toContain(j.patientId);
    });
  });

  it("analytics records reference valid patient IDs", () => {
    const patientIds = mockPatients.map((p) => p.id);
    mockPatientAnalytics.forEach((a) => {
      expect(patientIds).toContain(a.patientId);
    });
  });
});

// helper function tests

describe("getPatientById", () => {
  it("returns correct patient for valid ID", () => {
    const patient = getPatientById("p-001");
    expect(patient).toBeDefined();
    expect(patient!.id).toBe("p-001");
    expect(patient!.name).toBe("Alex Rivera");
  });

  it("returns each patient by their ID", () => {
    mockPatients.forEach((p) => {
      const found = getPatientById(p.id);
      expect(found).toBeDefined();
      expect(found!.id).toBe(p.id);
      expect(found!.name).toBe(p.name);
    });
  });

  it("returns undefined for non-existent ID", () => {
    expect(getPatientById("p-999")).toBeUndefined();
    expect(getPatientById("")).toBeUndefined();
    expect(getPatientById("invalid")).toBeUndefined();
  });
});

describe("getAnalyticsForPatient", () => {
  it("returns analytics for valid patient ID", () => {
    const analytics = getAnalyticsForPatient("p-001");
    expect(analytics).toBeDefined();
    expect(analytics!.patientId).toBe("p-001");
    expect(analytics!.totalEntries).toBe(47);
    expect(analytics!.themeDistribution.length).toBeGreaterThan(0);
  });

  it("returns analytics for each patient", () => {
    mockPatientAnalytics.forEach((a) => {
      const found = getAnalyticsForPatient(a.patientId);
      expect(found).toBeDefined();
      expect(found!.patientId).toBe(a.patientId);
    });
  });

  it("returns undefined for non-existent patient", () => {
    expect(getAnalyticsForPatient("p-999")).toBeUndefined();
    expect(getAnalyticsForPatient("")).toBeUndefined();
  });
});

describe("getJournalsForPatient", () => {
  it("returns journals for patient p-001 sorted by date descending", () => {
    const journals = getJournalsForPatient("p-001");
    expect(journals.length).toBe(5); // 5 entries for p-001

    // Verify all belong to p-001
    journals.forEach((j) => expect(j.patientId).toBe("p-001"));

    // Verify date descending order
    for (let i = 1; i < journals.length; i++) {
      const prev = new Date(journals[i - 1].entryDate).getTime();
      const curr = new Date(journals[i].entryDate).getTime();
      expect(prev).toBeGreaterThanOrEqual(curr);
    }
  });

  it("returns journals for patient p-002", () => {
    const journals = getJournalsForPatient("p-002");
    expect(journals.length).toBe(2);
    journals.forEach((j) => expect(j.patientId).toBe("p-002"));
  });

  it("returns empty array for patient with no journals", () => {
    expect(getJournalsForPatient("p-999")).toEqual([]);
    expect(getJournalsForPatient("")).toEqual([]);
  });

  it("returns 1 entry each for p-003, p-004, p-005", () => {
    expect(getJournalsForPatient("p-003").length).toBe(1);
    expect(getJournalsForPatient("p-004").length).toBe(1);
    expect(getJournalsForPatient("p-005").length).toBe(1);
  });

  it("does not mutate the original entries array", () => {
    const original = [...mockJournalEntries];
    getJournalsForPatient("p-001");
    expect(mockJournalEntries).toEqual(original);
  });
});
