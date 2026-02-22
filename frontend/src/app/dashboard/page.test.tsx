import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

// mock auth
import { mockTherapist } from "@/__tests__/mock-api-data";
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

// mock api
import {
  mockPatients,
  mockDashboardStats,
  mockAnalytics,
  mockJournals,
  mockMoodTrend,
} from "@/__tests__/mock-api-data";

vi.mock("@/lib/api", () => ({
  fetchPatients: vi.fn(),
  fetchDashboardStats: vi.fn(),
  fetchAnalytics: vi.fn(),
  fetchJournals: vi.fn(),
  fetchMoodTrend: vi.fn(),
}));

import { fetchPatients, fetchDashboardStats, fetchAnalytics, fetchJournals, fetchMoodTrend } from "@/lib/api";
import DashboardPage from "@/app/dashboard/page";

describe("Dashboard overview page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatients).mockResolvedValue(mockPatients);
    vi.mocked(fetchDashboardStats).mockResolvedValue(mockDashboardStats);
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
    vi.mocked(fetchJournals).mockResolvedValue(mockJournals);
    vi.mocked(fetchMoodTrend).mockResolvedValue(mockMoodTrend);
  });

  it("renders without crashing", () => {
    render(<DashboardPage />);
  });

  it("displays stat cards", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Total Patients")).toBeInTheDocument();
      expect(screen.getByText("Journal Entries")).toBeInTheDocument();
      expect(screen.getByText("Conversations")).toBeInTheDocument();
      expect(screen.getByText("Active Patients")).toBeInTheDocument();
    });
  });

  it("shows stat values", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("5")).toBeInTheDocument(); // total patients
      expect(screen.getByText("196")).toBeInTheDocument(); // total journals
    });
  });

  it("displays the patient list", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
      expect(screen.getByText("Jordan Kim")).toBeInTheDocument();
    });
  });

  it("renders patient list items", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("Morgan Patel")).toBeInTheDocument();
      expect(screen.getByText("Casey Thompson")).toBeInTheDocument();
      expect(screen.getByText("Taylor Nguyen")).toBeInTheDocument();
    });
  });

  it("shows the RAG assistant panel", async () => {
    render(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText("RAG Assistant")).toBeInTheDocument();
    });
  });
});
