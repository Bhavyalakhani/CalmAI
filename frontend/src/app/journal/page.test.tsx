import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

import { mockPatient, mockJournals, mockMoodTrend } from "@/__tests__/mock-api-data";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockPatient,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  fetchJournals: vi.fn(),
  fetchMoodTrend: vi.fn(),
  submitJournal: vi.fn(),
}));

import { fetchJournals, fetchMoodTrend, submitJournal } from "@/lib/api";
import JournalPage from "@/app/journal/page";

describe("Journal page", () => {
  beforeEach(() => {
    vi.mocked(fetchJournals).mockResolvedValue(mockJournals);
    vi.mocked(fetchMoodTrend).mockResolvedValue(mockMoodTrend);
    vi.mocked(submitJournal).mockResolvedValue({ journalId: "j-new", message: "Entry saved successfully!" });
  });

  it("renders without crashing", () => {
    render(<JournalPage />);
  });

  it("displays the new entry textarea", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("New Journal Entry")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Start writing...")).toBeInTheDocument();
    });
  });

  it("displays Save Entry button", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("Save Entry")).toBeInTheDocument();
    });
  });

  it("Save Entry button is disabled when textarea is empty", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      const btn = screen.getByText("Save Entry").closest("button");
      expect(btn).toBeDisabled();
    });
  });

  it("enables Save Entry button when content is typed", async () => {
    const user = userEvent.setup();
    render(<JournalPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Start writing...")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Start writing..."), "Today was a great day");

    const btn = screen.getByText("Save Entry").closest("button");
    expect(btn).not.toBeDisabled();
  });

  it("computes word count from typed content", async () => {
    const user = userEvent.setup();
    render(<JournalPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Start writing...")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Start writing..."), "Hello world today");

    expect(screen.getByText("3 words")).toBeInTheDocument();
  });

  it("shows 0 words when textarea is empty", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("0 words")).toBeInTheDocument();
    });
  });

  it("displays mood selector", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("How are you feeling?")).toBeInTheDocument();
      expect(screen.getAllByTitle("Very Low").length).toBeGreaterThan(0);
      expect(screen.getAllByTitle("Low").length).toBeGreaterThan(0);
      expect(screen.getAllByTitle("Okay").length).toBeGreaterThan(0);
      expect(screen.getAllByTitle("Good").length).toBeGreaterThan(0);
      expect(screen.getAllByTitle("Great").length).toBeGreaterThan(0);
    });
  });

  it("shows journal timeline section", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("Your Journal Timeline")).toBeInTheDocument();
      expect(screen.getByText("5 entries")).toBeInTheDocument();
    });
  });

  it("displays journal entry content in timeline", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/managed to get through work without feeling overwhelmed/)
      ).toBeInTheDocument();
    });
  });

  it("displays theme badges on entries", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getAllByText("anxiety").length).toBeGreaterThan(0);
    });
  });

  it("shows sidebar with mood trend", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("Your Mood This Week")).toBeInTheDocument();
    });
  });

  it("shows sidebar with stats", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("Your Stats")).toBeInTheDocument();
      expect(screen.getByText("Total entries")).toBeInTheDocument();
    });
  });

  it("shows therapist prompt in sidebar", async () => {
    render(<JournalPage />);
    await waitFor(() => {
      expect(screen.getByText("From Your Therapist")).toBeInTheDocument();
    });
  });

  it("shows saving state when entry is submitted", async () => {
    vi.mocked(submitJournal).mockReturnValue(new Promise(() => {}) as any); // never resolves
    const user = userEvent.setup();
    render(<JournalPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Start writing...")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Start writing..."), "Test content here");
    await user.click(screen.getByText("Save Entry"));

    expect(screen.getByText("Saving...")).toBeInTheDocument();
  });
});
