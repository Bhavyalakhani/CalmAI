import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// mock next/link as a plain anchor
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
    const links = screen.getAllByText("Start free trial");
    expect(links.length).toBeGreaterThan(0);
  });

  it("has a Log in link", () => {
    render(<Home />);
    const loginLinks = screen.getAllByText("Log in");
    expect(loginLinks.length).toBeGreaterThan(0);
  });

  it("renders six feature cards", () => {
    render(<Home />);
    expect(screen.getByText("Patient Journaling")).toBeInTheDocument();
    expect(screen.getByText("RAG-Powered Search")).toBeInTheDocument();
    expect(screen.getByText("Clinician-First Design")).toBeInTheDocument();
    expect(screen.getByText("Topic Trend Analysis")).toBeInTheDocument();
    expect(screen.getByText("Conversation Corpus")).toBeInTheDocument();
    expect(screen.getByText("Per-Patient Analytics")).toBeInTheDocument();
  });

  it("renders how it works section without step numbers", () => {
    render(<Home />);
    expect(screen.getByText("How it works")).toBeInTheDocument();
    expect(screen.getByText("Capture")).toBeInTheDocument();
    expect(screen.getByText("Analyze")).toBeInTheDocument();
    expect(screen.getByText("Retrieve")).toBeInTheDocument();
    // step number badges should not exist
    expect(screen.queryByText("1")).not.toBeInTheDocument();
    expect(screen.queryByText("2")).not.toBeInTheDocument();
    expect(screen.queryByText("3")).not.toBeInTheDocument();
  });

  it("renders pricing section with most popular badge and CTA buttons", () => {
    render(<Home />);
    expect(screen.getByText("Pricing")).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Professional")).toBeInTheDocument();
    expect(screen.getByText("Enterprise")).toBeInTheDocument();
    expect(screen.getByText("Most popular")).toBeInTheDocument();
    // each tier has a CTA button
    expect(screen.getByText("Get started")).toBeInTheDocument();
    expect(screen.getByText("Contact sales")).toBeInTheDocument();
  });

  it("renders the stats section with query time instead of dimensions", () => {
    render(<Home />);
    expect(screen.getByText("3,500+")).toBeInTheDocument();
    expect(screen.getByText("1,000+")).toBeInTheDocument();
    expect(screen.getByText("< 1s")).toBeInTheDocument();
    expect(screen.getByText("90%+")).toBeInTheDocument();
    // no embedding dimensions
    expect(screen.queryByText("384")).not.toBeInTheDocument();
  });

  it("renders updated trust indicators", () => {
    render(<Home />);
    expect(screen.getByText("Source-cited answers")).toBeInTheDocument();
    expect(screen.getByText("No diagnostic outputs")).toBeInTheDocument();
    expect(screen.getByText("Sub-second retrieval")).toBeInTheDocument();
    // no HIPAA
    expect(screen.queryByText(/HIPAA/)).not.toBeInTheDocument();
  });

  it("renders testimonials section", () => {
    render(<Home />);
    expect(screen.getByText("Testimonials")).toBeInTheDocument();
    expect(screen.getByText("Dr. Maya Rodriguez")).toBeInTheDocument();
    expect(screen.getByText("Dr. James Liu")).toBeInTheDocument();
    expect(screen.getByText("Sarah Kim")).toBeInTheDocument();
  });

  it("renders FAQ section with all questions", () => {
    render(<Home />);
    expect(screen.getByText("Frequently asked questions")).toBeInTheDocument();
    expect(screen.getByText("How does CalmAI keep patient data secure?")).toBeInTheDocument();
    expect(screen.getByText("Does CalmAI make diagnoses or treatment recommendations?")).toBeInTheDocument();
    expect(screen.getByText("How long does it take to get started?")).toBeInTheDocument();
  });

  it("contains no em dashes anywhere on the page", () => {
    const { container } = render(<Home />);
    const text = container.textContent || "";
    expect(text).not.toContain("\u2014"); // em dash
    expect(text).not.toContain("\u2013"); // en dash
  });

  it("renders a footer with copyright", () => {
    render(<Home />);
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(`${year} CalmAI`))).toBeInTheDocument();
  });
});
