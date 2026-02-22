import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

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
}));

import { fetchPatients, fetchAnalytics, fetchDashboardStats } from "@/lib/api";
import AnalyticsPage from "@/app/dashboard/analytics/page";

describe("Analytics page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatients).mockResolvedValue(mockPatients);
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
    vi.mocked(fetchDashboardStats).mockResolvedValue(mockDashboardStats);
  });

  it("renders without crashing", () => {
    render(<AnalyticsPage />);
  });

  it("displays analytics heading", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Analytics & Bias Reports")).toBeInTheDocument();
    });
  });

  it("shows summary stat cards", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Topics Tracked")).toBeInTheDocument();
      expect(screen.getByText("Journal Themes")).toBeInTheDocument();
    });
  });

  it("renders tab navigation", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => {
      expect(screen.getByText("Conversation Bias")).toBeInTheDocument();
      expect(screen.getByText("Journal Bias")).toBeInTheDocument();
      expect(screen.getByText("Patient Distribution")).toBeInTheDocument();
    });
  });
});
