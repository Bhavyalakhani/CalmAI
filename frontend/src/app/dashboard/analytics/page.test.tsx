import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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

import AnalyticsPage from "@/app/dashboard/analytics/page";

describe("Analytics page", () => {
  it("renders without crashing", () => {
    render(<AnalyticsPage />);
  });

  it("displays analytics heading", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Analytics & Bias Reports")).toBeInTheDocument();
  });

  it("shows summary stat cards", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Topics Tracked")).toBeInTheDocument();
    expect(screen.getByText("Journal Themes")).toBeInTheDocument();
  });

  it("renders tab navigation", () => {
    render(<AnalyticsPage />);
    expect(screen.getByText("Conversation Bias")).toBeInTheDocument();
    expect(screen.getByText("Journal Bias")).toBeInTheDocument();
    expect(screen.getByText("Patient Distribution")).toBeInTheDocument();
  });
});
