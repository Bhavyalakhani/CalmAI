import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock next/link as a plain anchor
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import Home from "@/app/page";

describe("Landing page", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("renders without crashing", () => {
    render(<Home />);
  });

  it("displays the CalmAI brand name", () => {
    render(<Home />);
    const brand = screen.getAllByText("CalmAI");
    expect(brand.length).toBeGreaterThan(0);
  });

  it("displays the hero headline", () => {
    render(<Home />);
    expect(screen.getByText("Clinical intelligence")).toBeInTheDocument();
    expect(screen.getByText("without the noise")).toBeInTheDocument();
  });

  it("displays the tagline for licensed therapists", () => {
    render(<Home />);
    expect(screen.getByText("Built for licensed therapists")).toBeInTheDocument();
  });

  it("has a Start free trial link", () => {
    render(<Home />);
    expect(screen.getByText("Start free trial")).toBeInTheDocument();
  });

  it("has a Log in link", () => {
    render(<Home />);
    const loginLinks = screen.getAllByText("Log in");
    expect(loginLinks.length).toBeGreaterThan(0);
  });

  it("renders three feature cards", () => {
    render(<Home />);
    expect(screen.getByText("Patient Journaling")).toBeInTheDocument();
    expect(screen.getByText("RAG-Powered Search")).toBeInTheDocument();
    expect(screen.getByText("Clinician-First Design")).toBeInTheDocument();
  });

  it("renders the stats section", () => {
    render(<Home />);
    expect(screen.getByText("3,500+")).toBeInTheDocument();
    expect(screen.getByText("1,000+")).toBeInTheDocument();
    expect(screen.getByText("384")).toBeInTheDocument();
    expect(screen.getByText("90%+")).toBeInTheDocument();
  });

  it("renders a footer with copyright", () => {
    render(<Home />);
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(`${year} CalmAI`))).toBeInTheDocument();
  });
});
