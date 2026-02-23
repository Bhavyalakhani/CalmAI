import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

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

import { mockTherapist, mockConversations } from "@/__tests__/mock-api-data";

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
  fetchConversations: vi.fn(),
  fetchConversationTopics: vi.fn(),
  fetchConversationSeverities: vi.fn(),
}));

import {
  fetchConversations,
  fetchConversationTopics,
  fetchConversationSeverities,
} from "@/lib/api";
import ConversationsPage from "@/app/dashboard/conversations/page";

describe("Conversations page", () => {
  beforeEach(() => {
    vi.mocked(fetchConversations).mockResolvedValue({
      conversations: mockConversations,
      total: mockConversations.length,
      page: 1,
      pageSize: 20,
    });
    vi.mocked(fetchConversationTopics).mockResolvedValue({
      topics: [
        { label: "anxiety", count: 120 },
        { label: "relationships", count: 85 },
      ],
    });
    vi.mocked(fetchConversationSeverities).mockResolvedValue({
      severities: [
        { label: "moderate", count: 12 },
        { label: "severe", count: 6 },
      ],
    });
  });

  it("renders without crashing", () => {
    render(<ConversationsPage />);
  });

  it("displays the conversations heading", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(screen.getByText("Conversation Explorer")).toBeInTheDocument();
    });
  });

  it("shows dropdown filters", async () => {
    render(<ConversationsPage />);
    // wait for full render cycle (conversations + topics load in parallel)
    await waitFor(() => {
      expect(screen.getByText(/panic attacks almost every day/)).toBeInTheDocument();
    });
    expect(screen.getByText("All Topics")).toBeInTheDocument();
    expect(screen.getByText("All Severities")).toBeInTheDocument();
    // dynamic topic tabs loaded from api
    expect(screen.getAllByText(/anxiety/i).length).toBeGreaterThan(0);
  });

  it("loads topic and severity options", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(screen.getByText(/panic attacks almost every day/)).toBeInTheDocument();
    });
    expect(fetchConversationTopics).toHaveBeenCalled();
    expect(fetchConversationSeverities).toHaveBeenCalled();
  });

  it("displays sample conversation content", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/panic attacks almost every day/)
      ).toBeInTheDocument();
    });
  });

  it("shows topic and severity badges", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("anxiety").length).toBeGreaterThan(0);
      expect(screen.getAllByText("severe").length).toBeGreaterThan(0);
    });
  });
});
