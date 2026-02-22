import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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

import PromptsPage from "@/app/journal/prompts/page";

describe("Journal prompts page", () => {
  it("renders without crashing", () => {
    render(<PromptsPage />);
  });

  it("displays the prompts heading", () => {
    render(<PromptsPage />);
    expect(screen.getByText("Therapist Prompts")).toBeInTheDocument();
  });

  it("shows pending prompt", () => {
    render(<PromptsPage />);
    expect(
      screen.getByText(/one moment where you noticed your anxiety/)
    ).toBeInTheDocument();
  });

  it("shows pending badge", () => {
    render(<PromptsPage />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows answered prompts", () => {
    render(<PromptsPage />);
    // 2 answered prompts
    const answered = screen.getAllByText("Answered");
    expect(answered.length).toBe(2);
  });

  it("shows prompt source as Dr. Sarah Chen", () => {
    render(<PromptsPage />);
    const sources = screen.getAllByText("Dr. Sarah Chen");
    expect(sources.length).toBeGreaterThan(0);
  });
});
