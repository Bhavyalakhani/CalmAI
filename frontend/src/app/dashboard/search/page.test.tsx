import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

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

import { mockTherapist, mockPatients } from "@/__tests__/mock-api-data";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockTherapist,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  fetchPatients: vi.fn(),
  ragSearch: vi.fn(),
}));

import { fetchPatients, ragSearch } from "@/lib/api";
import RAGAssistantPage from "@/app/dashboard/search/page";

describe("RAG Assistant page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatients).mockResolvedValue(mockPatients);
  });

  it("renders without crashing", () => {
    render(<RAGAssistantPage />);
  });

  it("displays the assistant heading", async () => {
    render(<RAGAssistantPage />);
    await waitFor(() => {
      expect(screen.getByText("RAG Assistant")).toBeInTheDocument();
    });
  });

  it("has a message input", async () => {
    render(<RAGAssistantPage />);
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/Ask a question/)
      ).toBeInTheDocument();
    });
  });

  it("displays suggestion chips in empty state", async () => {
    render(<RAGAssistantPage />);
    await waitFor(() => {
      expect(
        screen.getByText("What anxiety coping techniques have been discussed?")
      ).toBeInTheDocument();
    });
  });

  it("shows send button", async () => {
    render(<RAGAssistantPage />);
    await waitFor(() => {
      expect(screen.getByText("Send")).toBeInTheDocument();
    });
  });

  it("displays patient filter with all patients option", async () => {
    render(<RAGAssistantPage />);
    await waitFor(() => {
      expect(screen.getByText("Patient context")).toBeInTheDocument();
    });
  });

  it("shows clinical safety disclaimer", async () => {
    render(<RAGAssistantPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/clinical decisions are yours/)
      ).toBeInTheDocument();
    });
  });

  it("sends a message and displays response", async () => {
    vi.mocked(ragSearch).mockResolvedValue({
      query: "test query",
      results: [
        {
          content: "Patient expressed anxiety.",
          score: 0.92,
          source: "journal" as const,
          metadata: { patient_id: "p1", entry_date: "2025-06-10" },
        },
      ],
      generatedAnswer: "Based on the journals, anxiety themes are present.",
      sources: ["journal:p1:2025-06-10"],
    });

    render(<RAGAssistantPage />);

    const input = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(input, { target: { value: "test query" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByText("test query")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(
        screen.getByText(/anxiety themes are present/)
      ).toBeInTheDocument();
    });
  });

  it("shows error state on failed request", async () => {
    vi.mocked(ragSearch).mockRejectedValue(new Error("Network error"));

    render(<RAGAssistantPage />);

    const input = screen.getByPlaceholderText(/Ask a question/);
    fireEvent.change(input, { target: { value: "failing query" } });
    fireEvent.click(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
