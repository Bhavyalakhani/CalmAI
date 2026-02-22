import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

import JournalPage from "@/app/journal/page";

describe("Journal page", () => {
  it("renders without crashing", () => {
    render(<JournalPage />);
  });

  it("displays the new entry textarea", () => {
    render(<JournalPage />);
    expect(screen.getByText("New Journal Entry")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Start writing...")).toBeInTheDocument();
  });

  it("displays Save Entry button", () => {
    render(<JournalPage />);
    expect(screen.getByText("Save Entry")).toBeInTheDocument();
  });

  it("Save Entry button is disabled when textarea is empty", () => {
    render(<JournalPage />);
    const btn = screen.getByText("Save Entry").closest("button");
    expect(btn).toBeDisabled();
  });

  it("enables Save Entry button when content is typed", async () => {
    const user = userEvent.setup();
    render(<JournalPage />);

    await user.type(screen.getByPlaceholderText("Start writing..."), "Today was a great day");

    const btn = screen.getByText("Save Entry").closest("button");
    expect(btn).not.toBeDisabled();
  });

  it("computes word count from typed content", async () => {
    const user = userEvent.setup();
    render(<JournalPage />);

    await user.type(screen.getByPlaceholderText("Start writing..."), "Hello world today");

    expect(screen.getByText("3 words")).toBeInTheDocument();
  });

  it("shows 0 words when textarea is empty", () => {
    render(<JournalPage />);
    expect(screen.getByText("0 words")).toBeInTheDocument();
  });

  it("displays mood selector", () => {
    render(<JournalPage />);
    expect(screen.getByText("How are you feeling?")).toBeInTheDocument();
    // 5 mood options exist (some emojis may duplicate with entries)
    expect(screen.getAllByTitle("Very Low").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("Low").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("Okay").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("Good").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("Great").length).toBeGreaterThan(0);
  });

  it("shows journal timeline section", () => {
    render(<JournalPage />);
    expect(screen.getByText("Your Journal Timeline")).toBeInTheDocument();
    expect(screen.getByText("5 entries")).toBeInTheDocument(); // p-001 has 5 entries
  });

  it("displays journal entry content in timeline", () => {
    render(<JournalPage />);
    // First entry for p-001 should be visible
    expect(
      screen.getByText(/managed to get through work without feeling overwhelmed/)
    ).toBeInTheDocument();
  });

  it("displays theme badges on entries", () => {
    render(<JournalPage />);
    expect(screen.getAllByText("anxiety").length).toBeGreaterThan(0);
  });

  it("shows sidebar with mood trend", () => {
    render(<JournalPage />);
    expect(screen.getByText("Your Mood This Week")).toBeInTheDocument();
  });

  it("shows sidebar with stats", () => {
    render(<JournalPage />);
    expect(screen.getByText("Your Stats")).toBeInTheDocument();
    expect(screen.getByText("Total entries")).toBeInTheDocument();
  });

  it("shows therapist prompt in sidebar", () => {
    render(<JournalPage />);
    expect(screen.getByText("From Your Therapist")).toBeInTheDocument();
  });

  it("shows saving state when entry is submitted", async () => {
    const user = userEvent.setup();
    render(<JournalPage />);

    await user.type(screen.getByPlaceholderText("Start writing..."), "Test content here");
    await user.click(screen.getByText("Save Entry"));

    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });
});
