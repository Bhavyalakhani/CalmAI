import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/search",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import SearchPage from "@/app/dashboard/search/page";

describe("RAG search page", () => {
  it("renders without crashing", () => {
    render(<SearchPage />);
  });

  it("displays the search heading", () => {
    render(<SearchPage />);
    expect(screen.getByText("RAG-Powered Search")).toBeInTheDocument();
  });

  it("has a search input", () => {
    render(<SearchPage />);
    expect(
      screen.getByPlaceholderText(/What anxiety coping techniques/)
    ).toBeInTheDocument();
  });

  it("displays suggestion chips", () => {
    render(<SearchPage />);
    expect(
      screen.getByText("Show anxiety patterns for Alex")
    ).toBeInTheDocument();
  });
});
