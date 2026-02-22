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

import { mockPatient, mockAnalytics } from "@/__tests__/mock-api-data";

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
}));

import { fetchAnalytics } from "@/lib/api";
import InsightsPage from "@/app/journal/insights/page";

describe("Journal insights page", () => {
  beforeEach(() => {
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
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

  it("shows total entries stat", async () => {
    render(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByText("Total Entries")).toBeInTheDocument();
      expect(screen.getByText("47")).toBeInTheDocument();
    });
  });
});
