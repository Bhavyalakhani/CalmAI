import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/journal/settings",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockPatient } from "@/__tests__/mock-api-data";

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

import JournalSettingsPage from "@/app/journal/settings/page";

describe("Journal settings page", () => {
  it("renders without crashing", () => {
    render(<JournalSettingsPage />);
  });

  it("displays the settings heading", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows profile section", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Your personal information")).toBeInTheDocument();
  });

  it("populates patient name by default", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByDisplayValue("Alex Rivera")).toBeInTheDocument();
  });
});
