import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { mockPatient } from "@/__tests__/mock-api-data";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/journal",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

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

import JournalLayout from "@/app/journal/layout";

describe("Journal layout", () => {
  it("renders without crashing", () => {
    render(
      <JournalLayout>
        <div>Journal child</div>
      </JournalLayout>
    );
  });

  it("renders child content", () => {
    render(
      <JournalLayout>
        <div>Journal child content</div>
      </JournalLayout>
    );
    expect(screen.getByText("Journal child content")).toBeInTheDocument();
  });

  it("shows CalmAI branding", () => {
    render(
      <JournalLayout>
        <div />
      </JournalLayout>
    );
    expect(screen.getByText("CalmAI")).toBeInTheDocument();
  });

  it("shows journal navigation items", () => {
    render(
      <JournalLayout>
        <div />
      </JournalLayout>
    );
    expect(screen.getByText("Journal")).toBeInTheDocument();
    expect(screen.getByText("Insights")).toBeInTheDocument();
    expect(screen.getByText("Prompts")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows patient name", () => {
    render(
      <JournalLayout>
        <div />
      </JournalLayout>
    );
    expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
  });
});
