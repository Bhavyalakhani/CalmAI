import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { mockTherapist } from "@/__tests__/mock-api-data";

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

import DashboardLayout from "@/app/dashboard/layout";

function renderWithProvider(ui: React.ReactNode) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("Dashboard layout", () => {
  it("renders without crashing", () => {
    renderWithProvider(
      <DashboardLayout>
        <div>Test child content</div>
      </DashboardLayout>
    );
  });

  it("renders child content", () => {
    renderWithProvider(
      <DashboardLayout>
        <div>Dashboard child</div>
      </DashboardLayout>
    );
    expect(screen.getByText("Dashboard child")).toBeInTheDocument();
  });

  it("shows CalmAI branding in sidebar", () => {
    renderWithProvider(
      <DashboardLayout>
        <div />
      </DashboardLayout>
    );
    expect(screen.getByText("CalmAI")).toBeInTheDocument();
  });

  it("shows navigation items", () => {
    renderWithProvider(
      <DashboardLayout>
        <div />
      </DashboardLayout>
    );
    expect(screen.getAllByText("Overview").length).toBeGreaterThan(0);
    expect(screen.getByText("Patients")).toBeInTheDocument();
    expect(screen.getByText("Conversations")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("RAG Assistant")).toBeInTheDocument();
  });

  it("shows therapist name", () => {
    renderWithProvider(
      <DashboardLayout>
        <div />
      </DashboardLayout>
    );
    expect(screen.getByText("Dr. Sarah Chen")).toBeInTheDocument();
  });
});
