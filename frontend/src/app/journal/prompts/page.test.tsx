import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/journal/prompts",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockPatient, mockPrompts } from "@/__tests__/mock-api-data";

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
  fetchPrompts: vi.fn(),
}));

import { fetchPrompts } from "@/lib/api";
import PromptsPage from "@/app/journal/prompts/page";

describe("Journal prompts page", () => {
  beforeEach(() => {
    vi.mocked(fetchPrompts).mockResolvedValue(mockPrompts);
  });

  it("renders without crashing", () => {
    render(<PromptsPage />);
  });

  it("displays the prompts heading", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      expect(screen.getByText("Therapist Prompts")).toBeInTheDocument();
    });
  });

  it("shows pending prompt", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/one moment where you noticed your anxiety/)
      ).toBeInTheDocument();
    });
  });

  it("shows pending badge", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      expect(screen.getByText("Pending")).toBeInTheDocument();
    });
  });

  it("shows answered prompts", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      const answered = screen.getAllByText("Answered");
      expect(answered.length).toBe(2);
    });
  });

  it("shows prompt source as Dr. Sarah Chen", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      const sources = screen.getAllByText("Dr. Sarah Chen");
      expect(sources.length).toBeGreaterThan(0);
    });
  });

  it("shows Write Response button for pending prompts", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      expect(screen.getByText("Write Response")).toBeInTheDocument();
    });
  });

  it("shows responded content", async () => {
    render(<PromptsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Had a great chat with a friend/)).toBeInTheDocument();
    });
  });

  it("shows empty state when no prompts", async () => {
    vi.mocked(fetchPrompts).mockResolvedValue([]);
    render(<PromptsPage />);
    await waitFor(() => {
      expect(screen.getByText(/No prompts from your therapist yet/)).toBeInTheDocument();
    });
  });
});
