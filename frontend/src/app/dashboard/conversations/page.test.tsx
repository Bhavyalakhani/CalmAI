import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/conversations",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import ConversationsPage from "@/app/dashboard/conversations/page";

describe("Conversations page", () => {
  it("renders without crashing", () => {
    render(<ConversationsPage />);
  });

  it("displays the conversations heading", () => {
    render(<ConversationsPage />);
    expect(screen.getByText("Conversation Explorer")).toBeInTheDocument();
  });

  it("shows tab filters", () => {
    render(<ConversationsPage />);
    expect(screen.getByText("All Topics")).toBeInTheDocument();
    expect(screen.getByText("Anxiety")).toBeInTheDocument();
    expect(screen.getByText("Depression")).toBeInTheDocument();
  });

  it("displays sample conversation content", () => {
    render(<ConversationsPage />);
    expect(
      screen.getByText(/panic attacks almost every day/)
    ).toBeInTheDocument();
  });

  it("shows topic and severity badges", () => {
    render(<ConversationsPage />);
    expect(screen.getAllByText("anxiety").length).toBeGreaterThan(0);
    expect(screen.getAllByText("severe").length).toBeGreaterThan(0);
  });
});
