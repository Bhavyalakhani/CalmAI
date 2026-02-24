import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/analytics",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockTherapist, mockPatients, mockAnalytics, mockDashboardStats } from "@/__tests__/mock-api-data";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockTherapist,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  fetchPatients: vi.fn(),
  fetchAnalytics: vi.fn(),
  fetchDashboardStats: vi.fn(),
  fetchConversationTopics: vi.fn(),
  fetchConversationSeverities: vi.fn(),
}));

import {
  fetchPatients,
  fetchAnalytics,
  fetchDashboardStats,
  fetchConversationTopics,
  fetchConversationSeverities,
} from "@/lib/api";
import AnalyticsPage from "@/app/dashboard/analytics/page";

describe("Analytics page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatients).mockResolvedValue(mockPatients);
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
    vi.mocked(fetchDashboardStats).mockResolvedValue(mockDashboardStats);
    vi.mocked(fetchConversationTopics).mockResolvedValue({
      topics: [
        { label: "anxiety", count: 120 },
        { label: "sleep disruption", count: 45 },
      ],
    });
    vi.mocked(fetchConversationSeverities).mockResolvedValue({
      severities: [
        { label: "mild", count: 90 },
        { label: "moderate", count: 50 },
      ],
    });
  });

  it("renders without crashing", () => {
    render(<AnalyticsPage />);
  });

  it("displays patient analytics heading", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Patient Analytics")).toBeInTheDocument();
    });
  });

  it("shows summary stat cards", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Total Processed Entries")).toBeInTheDocument();
      expect(screen.getByText("Avg. Word Count")).toBeInTheDocument();
      // "Conversations Corpus" appears both in summary card and tab
      expect(screen.getAllByText("Conversations Corpus").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Active Patients")).toBeInTheDocument();
    });
  });

  it("renders tab navigation", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Patient Deep Dive")).toBeInTheDocument();
      expect(screen.getByText("Patient Comparison")).toBeInTheDocument();
      // corpus tab shares text with summary card
      expect(screen.getAllByText("Conversations Corpus").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows patient selector in deep dive tab", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Patient:")).toBeInTheDocument();
    });
  });

  it("displays topic distribution when patient has analytics", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Topic Distribution")).toBeInTheDocument();
    });
  });

  it("displays entry frequency card", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Entry Frequency")).toBeInTheDocument();
    });
  });

  it("shows patient overview stats when patient has analytics", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      // overview card should show total entries, avg word count, date span, topics count
      expect(screen.getByText("Processed entries")).toBeInTheDocument();
      expect(screen.getByText("Avg. words / entry")).toBeInTheDocument();
      expect(screen.getByText("Date span (days)")).toBeInTheDocument();
      expect(screen.getByText("Topics identified")).toBeInTheDocument();
    });
  });

  it("shows no analytics empty state when patient lacks data", async () => {
    // all analytics calls reject so no patient has data
    vi.mocked(fetchAnalytics).mockRejectedValue(new Error("not found"));
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("No analytics available")).toBeInTheDocument();
      expect(screen.getByText(/Run the data pipeline/)).toBeInTheDocument();
    });
  });

  it("renders topics over time card", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Topics Over Time")).toBeInTheDocument();
      // mock data has months 2025-01 and 2025-02 (may appear in multiple places)
      expect(screen.getAllByText("2025-01").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders representative entries with confidence", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Representative Entries")).toBeInTheDocument();
      // mock entry: "feeling very anxious today" with 92% confidence
      expect(screen.getByText(/feeling very anxious today/)).toBeInTheDocument();
      expect(screen.getByText(/92% confidence/)).toBeInTheDocument();
    });
  });

  it("has patient comparison tab with correct trigger", async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Patient Comparison" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("tab", { name: "Patient Comparison" }));
    await waitFor(() => {
      expect(screen.getByText("Processed Entries per Patient")).toBeInTheDocument();
      expect(screen.getByText("Top Topics per Patient")).toBeInTheDocument();
      expect(screen.getByText("Journaling Span")).toBeInTheDocument();
    });
  });

  it("has conversation corpus tab with topic and severity content", async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Conversations Corpus" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("tab", { name: "Conversations Corpus" }));
    await waitFor(() => {
      expect(screen.getByText("Conversations Topic Distribution")).toBeInTheDocument();
      expect(screen.getByText("Severity Distribution")).toBeInTheDocument();
    });
  });

  it("shows loading skeleton while data loads", () => {
    // make fetches never resolve
    vi.mocked(fetchPatients).mockReturnValue(new Promise(() => {}));
    render(<AnalyticsPage />);
    // skeleton containers render immediately (no waitFor needed)
    const skeletons = document.querySelectorAll("[class*='skeleton'], [data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
