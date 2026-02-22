import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

import DashboardPage from "@/app/dashboard/page";

describe("Dashboard overview page", () => {
  it("renders without crashing", () => {
    render(<DashboardPage />);
  });

  it("displays stat cards", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Total Patients")).toBeInTheDocument();
    expect(screen.getByText("Journal Entries")).toBeInTheDocument();
    expect(screen.getByText("Conversations")).toBeInTheDocument();
    expect(screen.getByText("Active Patients")).toBeInTheDocument();
  });

  it("shows stat values", () => {
    render(<DashboardPage />);
    expect(screen.getByText("5")).toBeInTheDocument(); // total patients
    expect(screen.getByText("196")).toBeInTheDocument(); // total journals
  });

  it("displays the patient list", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
    expect(screen.getByText("Jordan Kim")).toBeInTheDocument();
  });

  it("renders patient list items", () => {
    render(<DashboardPage />);
    // All patients should be visible in the list
    expect(screen.getByText("Morgan Patel")).toBeInTheDocument();
    expect(screen.getByText("Casey Thompson")).toBeInTheDocument();
    expect(screen.getByText("Taylor Nguyen")).toBeInTheDocument();
  });

  it("shows the RAG assistant panel", () => {
    render(<DashboardPage />);
    expect(screen.getByText("RAG Assistant")).toBeInTheDocument();
  });
});
