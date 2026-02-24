import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
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

const mockLogout = vi.fn();

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockPatient,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: mockLogout,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  changePassword: vi.fn(),
  deleteAccount: vi.fn().mockResolvedValue(undefined),
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

  it("shows therapist name from patient data", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByText("Dr. Sarah Chen")).toBeInTheDocument();
  });

  it("shows therapist specialization and license", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByText(/Cognitive Behavioral Therapy/)).toBeInTheDocument();
    expect(screen.getByText(/PSY-2024-11892/)).toBeInTheDocument();
  });

  it("shows change password section", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByLabelText("Current password")).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();
  });

  it("shows privacy section", () => {
    render(<JournalSettingsPage />);
    expect(screen.getByText("Privacy")).toBeInTheDocument();
    expect(screen.getByText(/encryption at rest/)).toBeInTheDocument();
  });

  it("shows delete account section", () => {
    render(<JournalSettingsPage />);
    expect(screen.getAllByText("Delete Account").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/permanently delete/i).length).toBeGreaterThan(0);
  });

  it("shows delete account button", () => {
    render(<JournalSettingsPage />);
    const deleteButtons = screen.getAllByRole("button", { name: /delete account/i });
    expect(deleteButtons.length).toBeGreaterThan(0);
  });
});
