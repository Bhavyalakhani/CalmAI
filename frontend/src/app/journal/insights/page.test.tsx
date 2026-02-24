import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/journal/insights",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockPatient, mockAnalytics, mockMoodTrend, mockJournals } from "@/__tests__/mock-api-data";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockPatient,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  fetchAnalytics: vi.fn(),
  fetchMoodTrend: vi.fn(),
  fetchJournals: vi.fn(),
}));

import { fetchAnalytics, fetchMoodTrend, fetchJournals } from "@/lib/api";
import InsightsPage from "@/app/journal/insights/page";

describe("Journal insights page", () => {
  beforeEach(() => {
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
    vi.mocked(fetchMoodTrend).mockResolvedValue(mockMoodTrend);
    vi.mocked(fetchJournals).mockResolvedValue(mockJournals);
  });

  it("renders without crashing", () => {
    render(<InsightsPage />);
  });

  it("displays the insights heading", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Your Insights")).toBeInTheDocument();
    });
  });

  it("shows disclaimer about patterns", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/patterns, not diagnoses/)
      ).toBeInTheDocument();
    });
  });

  it("shows processed entries stat", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Processed Entries")).toBeInTheDocument();
      expect(screen.getByText("47")).toBeInTheDocument();
    });
  });

  it("shows writing streak stat", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Writing Streak")).toBeInTheDocument();
    });
  });

  it("shows mood trend section with average", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Mood Trend (30 days)")).toBeInTheDocument();
      // avg of mockMoodTrend: (3+5+3+2+4+4+4)/7 = 3.6
      expect(screen.getByText("3.6")).toBeInTheDocument();
    });
  });

  it("shows topic distribution section", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Topic Distribution")).toBeInTheDocument();
      expect(screen.getAllByText("anxiety & stress").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows topics over time section", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Topics Over Time")).toBeInTheDocument();
    });
  });

  it("shows representative entries section", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Representative Entries")).toBeInTheDocument();
      expect(screen.getByText("feeling very anxious today")).toBeInTheDocument();
    });
  });

  it("shows monthly writing frequency", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Monthly Writing Frequency")).toBeInTheDocument();
    });
  });

  it("shows avg words stat", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Avg. Words")).toBeInTheDocument();
      expect(screen.getByText("24")).toBeInTheDocument();
    });
  });

  it("shows no data message when analytics is null", async () => {
    vi.mocked(fetchAnalytics).mockResolvedValue(null as unknown as typeof mockAnalytics);
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("No analytics data available.")).toBeInTheDocument();
    });
  });
});
