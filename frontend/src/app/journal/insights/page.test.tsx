import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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

import InsightsPage from "@/app/journal/insights/page";

describe("Journal insights page", () => {
  it("renders without crashing", () => {
    render(<InsightsPage />);
  });

  it("displays the insights heading", () => {
    render(<InsightsPage />);
    expect(screen.getByText("Your Insights")).toBeInTheDocument();
  });

  it("shows disclaimer about patterns", () => {
    render(<InsightsPage />);
    expect(
      screen.getByText(/patterns, not diagnoses/)
    ).toBeInTheDocument();
  });

  it("shows total entries stat", () => {
    render(<InsightsPage />);
    expect(screen.getByText("Total Entries")).toBeInTheDocument();
    expect(screen.getByText("47")).toBeInTheDocument(); // p-001 analytics
  });
});
